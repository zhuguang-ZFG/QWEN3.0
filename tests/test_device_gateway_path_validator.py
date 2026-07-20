"""Tests for device_gateway.path_validator."""

from device_gateway.path_validator import (
    validate_capability_params,
    validate_run_path_params,
    CAPABILITY_PATH_MAP,
    MAX_PATH_POINTS,
)


def test_validate_run_path_params_accepts_valid_path():
    params = {"path": [{"x": 10, "y": 20, "z": 0}], "feed": 500}
    sanitized, error = validate_run_path_params(params)
    assert error is None
    assert len(sanitized["path"]) == 1


def test_validate_run_path_params_rejects_empty_path():
    _, error = validate_run_path_params({"path": [], "feed": 500})
    assert error == "E_MISSING_PATH"


def test_validate_run_path_params_rejects_missing_path():
    _, error = validate_run_path_params({"feed": 500})
    assert error == "E_MISSING_PATH"


def test_validate_run_path_params_rejects_non_dict_params():
    _, error = validate_run_path_params("not a dict")
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_oversized_path():
    path = [{"x": 0, "y": 0, "z": 0}] * (MAX_PATH_POINTS + 1)
    _, error = validate_run_path_params({"path": path, "feed": 500})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_out_of_bounds_point():
    _, error = validate_run_path_params({"path": [{"x": 9999, "y": 0, "z": 0}], "feed": 500})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_invalid_feed():
    _, error = validate_run_path_params({"path": [{"x": 0, "y": 0, "z": 0}], "feed": 9999})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_rejects_nan_feed():
    """GW-R3-1: NaN feed must not pass range checks."""
    _, error = validate_run_path_params({"path": [{"x": 0, "y": 0, "z": 0}], "feed": float("nan")})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_allows_large_coord_without_profile():
    """GW-R3-5 fix: no-profile pre-check falls back to the ±500 hard limit.

    Real product firmware advertises a 300x300x80mm workspace; the app-create
    pre-check runs before the profile resolves, so clamping to the 100mm
    DEFAULT_WORKSPACE_MM here rejected legitimate coords. Profile-aware
    [0, workspace] enforcement still happens once the profile is resolved
    (see the profile test below).
    """
    _, error = validate_run_path_params({"path": [{"x": 250, "y": 0, "z": 0}], "feed": 500})
    assert error is None


def test_validate_run_path_params_still_rejects_beyond_hard_limit_without_profile():
    """GW-R3-5 fix: the absolute ±500 defense-in-depth limit still applies."""
    _, error = validate_run_path_params({"path": [{"x": 600, "y": 0, "z": 0}], "feed": 500})
    assert error == "E_BAD_PARAMS"


def test_validate_run_path_params_enforces_profile_workspace_when_resolved():
    """Profile-aware [0, workspace] enforcement rejects coords outside the box."""
    from device_intelligence.schemas import DeviceProfile

    profile = DeviceProfile(profile_id="small", model="small", workspace_mm={"x": 100, "y": 100, "z": 20})
    _, error = validate_run_path_params({"path": [{"x": 250, "y": 0, "z": 0}], "feed": 500}, profile=profile)
    assert error == "E_BAD_PARAMS"


def test_validate_capability_params_rejects_unknown_capability():
    _, error = validate_capability_params("laser_engrave", {"path": [{"x": 0, "y": 0}], "feed": 500})
    assert error == "E_UNSUPPORTED_CAPABILITY"


def test_validate_capability_params_accepts_write_text_with_text_field():
    params = {"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500, "text": "hello"}
    sanitized, error = validate_capability_params("write_text", params)
    assert error is None
    assert sanitized["text"] == "hello"


def test_validate_capability_params_rejects_write_text_without_text():
    params = {"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500}
    _, error = validate_capability_params("write_text", params)
    assert error == "E_BAD_PARAMS"


def test_validate_capability_params_preserves_preview_svg():
    preview = "<svg>" + ("x" * 300) + "</svg>"
    params = {
        "path": [{"x": 0, "y": 0, "z": 0}],
        "feed": 500,
        "text": "hello",
        "preview_svg": preview,
    }

    sanitized, error = validate_capability_params("write_text", params)

    assert error is None
    assert sanitized["preview_svg"].endswith("</svg>")
    assert len(sanitized["preview_svg"]) > 120


def test_validate_capability_params_accepts_control_capability_without_path():
    sanitized, error = validate_capability_params("home", {"source_capability": "home"})

    assert error is None
    assert sanitized == {"source_capability": "home"}


def test_capability_path_map_covers_active_capabilities():
    for cap in ("run_path", "write_text", "draw_generated", "home", "pause", "resume", "stop", "get_device_info"):
        assert cap in CAPABILITY_PATH_MAP
