"""2026-07-20 第二轮审查 域 B 边界校验回归测试。

覆盖:
- B3 (CORE-O4)  NaN/Inf/非正 workspace 整体绕过边界校验
- B2 (GW-B2)    _normalize_path_to_workspace 退化跨度不缩放
- B1 (GW-B1)    路径生成类能力(write_text 等)绕过工作区归一化

队列语义(B4/B5/B7)见 test_review_round2_domain_b_queue.py。
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from device_gateway.path_pipeline import (
    PathNormalizationError,
    _normalize_path_to_workspace,
    render_svg_task,
    render_text_task,
)
from dlc_api.schemas import TaskValidateRequest
from dlc_core.path_validator import validate_path


# ── B3: workspace bounds must be finite and positive ─────────────────────────


def test_validate_path_rejects_nan_workspace():
    """复现基线：修前 NaN workspace 对任意坐标返回 ok=True。"""
    result = validate_path(
        [{"x": 999999, "y": 999999}],
        workspace={"x": float("nan"), "y": float("nan")},
    )
    assert result["ok"] is False
    assert any("workspace bound" in e for e in result["errors"])


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), -10.0, 0.0, "100"])
def test_validate_path_rejects_non_finite_or_non_positive_bounds(bad):
    result = validate_path([{"x": 10, "y": 10}], workspace={"x": bad, "y": 100.0, "z": 20.0})
    assert result["ok"] is False


def test_validate_path_accepts_valid_workspace():
    result = validate_path([{"x": 10, "y": 10}], workspace={"x": 100.0, "y": 100.0, "z": 20.0})
    assert result["ok"] is True


def test_task_validate_request_rejects_nan_workspace_at_parse():
    with pytest.raises(ValidationError):
        TaskValidateRequest(path=[{"x": 1, "y": 1}], workspace={"x": float("nan"), "y": 100.0})


def test_task_validate_request_rejects_inf_workspace_at_parse():
    with pytest.raises(ValidationError):
        TaskValidateRequest(path=[{"x": 1, "y": 1}], workspace={"x": float("inf"), "y": 100.0})


# ── B2: degenerate spans must scale per-axis; out-of-bounds rejects ───────────


def test_horizontal_line_scaled_into_workspace():
    """复现基线：修前 render_svg_task('M 0 0 L 400 0') 输出 x∈[2,197]。"""
    result = render_svg_task("M 0 0 L 400 0")
    xs = [p["x"] for p in result["path"]]
    ys = [p["y"] for p in result["path"]]
    assert max(xs) <= 100.0 and min(xs) >= 0.0
    assert max(ys) <= 100.0 and min(ys) >= 0.0


def test_vertical_line_scaled_into_workspace():
    result = render_svg_task("M 0 0 L 0 400")
    assert all(0.0 <= p["y"] <= 100.0 and 0.0 <= p["x"] <= 100.0 for p in result["path"])


def test_normalize_single_point_stays_in_workspace():
    path = _normalize_path_to_workspace([{"x": 5.0, "y": 5.0}], width=100.0, height=100.0)
    assert 0.0 <= path[0]["x"] <= 100.0
    assert 0.0 <= path[0]["y"] <= 100.0


def test_normalize_rejects_nan_coordinates():
    with pytest.raises(PathNormalizationError):
        _normalize_path_to_workspace([{"x": math.nan, "y": 0.0}, {"x": 1.0, "y": 1.0}])


# ── B1: generated text paths pass workspace normalization ────────────────────


def test_render_text_long_text_within_default_workspace():
    """复现基线：修前 render_text_task('HELLO WORLD ABC') max_x=183mm。"""
    result = render_text_task("HELLO WORLD ABC")
    xs = [p["x"] for p in result["path"]]
    ys = [p["y"] for p in result["path"]]
    assert max(xs) <= 100.0 and min(xs) >= 0.0
    assert max(ys) <= 100.0 and min(ys) >= 0.0


def test_render_text_short_text_size_not_regressed():
    """正常短文本不因归一化被误伤缩小（scale 上限 1.0，只平移不缩放）。"""
    from device_gateway.path_pipeline import text_to_path

    raw = text_to_path("Hi")
    raw_span_x = max(p["x"] for p in raw) - min(p["x"] for p in raw)
    result = render_text_task("Hi", optimize=False)
    xs = [p["x"] for p in result["path"]]
    assert (max(xs) - min(xs)) == pytest.approx(raw_span_x, abs=0.05)


@pytest.mark.asyncio
async def test_write_text_e2e_long_text_small_workspace():
    """端到端：未知设备解析保守 profile(60mm)，长文本坐标必须在界内或被拒。"""
    from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests

    reset_tasks_for_tests()
    try:
        task = await project_to_motion_task_async(
            "dev-b1-e2e",
            {"capability": "write_text", "params": {"text": "HELLO WORLD ABC", "feed": 500}, "source": "api"},
        )
        if not task.get("error"):
            path = task["params"]["path"]
            assert path, "write_text task must carry a path"
            assert all(0.0 <= p["x"] <= 60.0 and 0.0 <= p["y"] <= 60.0 for p in path)
    finally:
        reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_write_text_e2e_short_text_still_accepted():
    """正常短文本在保守 profile 下不能被误拒。"""
    from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests

    reset_tasks_for_tests()
    try:
        task = await project_to_motion_task_async(
            "dev-b1-short",
            {"capability": "write_text", "params": {"text": "Hi", "feed": 500}, "source": "api"},
        )
        assert not task.get("error"), f"short text must not be rejected: {task.get('error')}"
        assert all(0.0 <= p["x"] <= 60.0 and 0.0 <= p["y"] <= 60.0 for p in task["params"]["path"])
    finally:
        reset_tasks_for_tests()
