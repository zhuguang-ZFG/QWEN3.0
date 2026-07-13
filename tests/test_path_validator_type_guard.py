"""path_validator 健壮性：非数值坐标应返回校验错误，而非抛 TypeError→500。

findings.md:585 记录的缺口：`validate_path` 的 `x < 0` 比较在 x/y 为非数值
（字符串/None/list）时抛 TypeError，冒泡成 500。应作为结构化校验错误返回
（ok=False + errors），让调用方拿到 400 级的清晰反馈而非 500。

同时补点数硬上限：超大 path（如 >5000 点）应拒绝（errors），不只是 warning，
防止恶意超大 path 耗尽绘图机 / 下游处理。

RED until validate_path type-guards coordinates and enforces a hard point cap.
"""

from __future__ import annotations

from dlc_core.path_validator import validate_path


def test_non_numeric_x_returns_error_not_raises() -> None:
    """x 为字符串时应返回 ok=False + 明确 error，不抛异常。"""
    result = validate_path([{"x": "abc", "y": 5}])
    assert result["ok"] is False
    assert any("point 0" in e for e in result["errors"]), result


def test_non_numeric_y_returns_error() -> None:
    result = validate_path([{"x": 5, "y": [1, 2]}])
    assert result["ok"] is False
    assert any("point 0" in e for e in result["errors"]), result


def test_bool_coordinate_rejected() -> None:
    """bool 是 int 子类但坐标语义上非法，应拒绝（避免 True==1 混入）。"""
    result = validate_path([{"x": True, "y": 5}])
    assert result["ok"] is False


def test_valid_numeric_still_passes() -> None:
    """合法数值（int/float）仍通过。"""
    result = validate_path([{"x": 10, "y": 20.5}])
    assert result["ok"] is True
    assert result["errors"] == []


def test_hard_point_cap_rejected() -> None:
    """超过硬上限的 path 应返回 error（拒绝），而非仅 warning。"""
    huge = [{"x": 1, "y": 1} for _ in range(5001)]
    result = validate_path(huge)
    assert result["ok"] is False
    assert any("exceeds" in e or "too many" in e.lower() for e in result["errors"]), result


def test_soft_warning_still_present() -> None:
    """200-5000 之间仍是 warning（不拒绝），保持既有语义。"""
    mid = [{"x": 1, "y": 1} for _ in range(300)]
    result = validate_path(mid)
    assert result["ok"] is True
    assert any("200" in w for w in result["warnings"]), result


def test_nan_x_returns_error() -> None:
    """NaN x 应因非有限值被拒绝。"""
    result = validate_path([{"x": float("nan"), "y": 5}])
    assert result["ok"] is False
    assert any("point 0" in e for e in result["errors"]), result


def test_nan_y_returns_error() -> None:
    """NaN y 应因非有限值被拒绝。"""
    result = validate_path([{"x": 5, "y": float("nan")}])
    assert result["ok"] is False
    assert any("point 0" in e for e in result["errors"]), result


def test_inf_x_returns_error() -> None:
    """Inf/-Inf x 应因非有限值被拒绝。"""
    for val in (float("inf"), float("-inf")):
        result = validate_path([{"x": val, "y": 5}])
        assert result["ok"] is False
        assert any("point 0" in e for e in result["errors"]), result


def test_inf_y_returns_error() -> None:
    """Inf/-Inf y 应因非有限值被拒绝。"""
    for val in (float("inf"), float("-inf")):
        result = validate_path([{"x": 5, "y": val}])
        assert result["ok"] is False
        assert any("point 0" in e for e in result["errors"]), result
