"""Round-3 blocker regressions (GW-R3-1/3/4/5 + SEC-06 + ack gen)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from device_gateway.path_pipeline import (
    PathNormalizationError,
    _assert_path_within_workspace,
    render_svg_task,
)
from device_gateway.path_validator import validate_run_path_params
from device_gateway.redis_store_helpers import validate_task_schema
from device_intelligence.safety import profile_limit_error


def test_r3_1_nan_feed_rejected() -> None:
    _, err = validate_run_path_params({"path": [{"x": 1, "y": 1, "z": 0}], "feed": float("nan")})
    assert err == "E_BAD_PARAMS"


def test_r3_3_nan_workspace_profile_rejected() -> None:
    profile = SimpleNamespace(
        workspace_mm={"x": float("nan"), "y": 100.0, "z": 20.0},
        max_feed=1200,
        max_path_points=200,
    )
    err = profile_limit_error({"path": [{"x": 1, "y": 1, "z": 0}], "feed": 100}, profile)
    assert err == "E_BAD_PARAMS"


def test_r3_5_no_profile_allows_300mm_hardware_coord() -> None:
    """GW-R3-5 (revised): no-profile pre-check falls back to the ±500 hard limit.

    Real product firmware advertises a 300x300x80mm workspace, so a coord in
    (100, 500] must not be rejected before the profile resolves. Profile-aware
    [0, workspace] enforcement still runs in profile_limit_error downstream.
    """
    _, err = validate_run_path_params({"path": [{"x": 300, "y": 0, "z": 0}], "feed": 500})
    assert err is None


def test_r3_5_no_profile_still_rejects_beyond_hard_limit() -> None:
    _, err = validate_run_path_params({"path": [{"x": 600, "y": 0, "z": 0}], "feed": 500})
    assert err == "E_BAD_PARAMS"


def test_r3_4_sec06_rejects_oob_path_on_queue() -> None:
    assert (
        validate_task_schema(
            {
                "task_id": "t-oob",
                "device_id": "dev-1",
                "capability": "run_path",
                "params": {"path": [{"x": 9999, "y": 0, "z": 0}], "feed": 500},
            }
        )
        is False
    )


def test_r3_4_sec06_accepts_in_bounds_run_path() -> None:
    assert (
        validate_task_schema(
            {
                "task_id": "t-ok",
                "device_id": "dev-1",
                "capability": "run_path",
                "params": {"path": [{"x": 10, "y": 10, "z": 0}], "feed": 500},
            }
        )
        is True
    )


def test_r3_1_finite_feed_still_ok() -> None:
    sanitized, err = validate_run_path_params({"path": [{"x": 1, "y": 1, "z": 0}], "feed": 500})
    assert err is None
    assert math.isfinite(sanitized["feed"])


def test_r3_7_post_transform_assertion_rejects_out_of_bounds() -> None:
    """GW-R3-7: the post-transform assertion must reject a point a multi_pass
    offset pushed past the workspace (normalize-time check ran before the shift).
    """
    pushed = [{"x": 99.0, "y": 10.0, "z": 0}, {"x": 130.0, "y": 10.0, "z": 0}]
    with pytest.raises(PathNormalizationError):
        _assert_path_within_workspace(pushed, 100.0, 100.0, stage="test")


def test_r3_7_normal_render_still_within_bounds() -> None:
    """GW-R3-7: a normal single-pass render stays in bounds (no false trip)."""
    result = render_svg_task("M 0 0 L 30 0 L 30 30 L 0 30 Z")
    assert all(0.0 <= p["x"] <= 100.0 and 0.0 <= p["y"] <= 100.0 for p in result["path"])


def test_r3_10_draw_clamp_feed_rejects_nonfinite() -> None:
    """GW-R3-10: NaN/Inf feed must fall back to the default, not silently clamp to
    MAX_FEED (2000, above the 1200 safety cap). Aligns draw with handwriting."""
    from device_gateway.safety import DEFAULT_FEED
    from device_gateway.task_draw_params import _clamp_feed

    assert _clamp_feed(float("nan")) == DEFAULT_FEED
    assert _clamp_feed(float("inf")) == DEFAULT_FEED
    assert _clamp_feed(float("-inf")) == DEFAULT_FEED
    # finite values still clamp normally
    assert _clamp_feed(999) == 999


def test_r3_6_handwriting_bounds_precheck_fails_closed(monkeypatch) -> None:
    """GW-R3-6: when the bounds precheck itself raises (import/bug), the
    handwriting path must fail closed (return an error) instead of returning
    None (= treated as in-bounds and dispatched)."""
    import device_gateway.path_pipeline as pp
    from device_gateway.handwriting_path import _check_motion_bounds

    def _boom(_svg: str) -> str | None:
        raise RuntimeError("precheck exploded")

    monkeypatch.setattr(pp, "precheck_draw_motion_path", _boom)
    result = _check_motion_bounds("M 0 0 L 10 10")
    assert result is not None
    assert "error" in result
