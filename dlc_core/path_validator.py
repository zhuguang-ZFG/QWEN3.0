"""Path validation facade for DLC core."""

from __future__ import annotations

from typing import Any

from dlc_core.safety import DEFAULT_WORKSPACE_MM, MAX_PATH_POINTS

# 硬点数上限：超过即拒绝（防畸形/恶意超大 path）。MAX_PATH_POINTS（200）是软阈值（warning）。
HARD_MAX_PATH_POINTS = 5000


def _is_number(value: Any) -> bool:
    """坐标必须是真数值：int/float 但排除 bool（bool 是 int 子类但语义非法）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_path(path: list[dict], *, workspace: dict[str, float] | None = None) -> dict[str, Any]:
    """Validate a motion path against workspace bounds and safety rules.

    Returns:
        {"ok": bool, "errors": list[str], "warnings": list[str]}
    """
    bounds = workspace or DEFAULT_WORKSPACE_MM
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(path, list) or len(path) == 0:
        errors.append("path is empty")
        return {"ok": False, "errors": errors, "warnings": warnings}

    # 硬点数上限：防止畸形/恶意超大 path 拖垮下游生成与设备执行。
    # MAX_PATH_POINTS（200）是软阈值（warning），HARD_MAX_PATH_POINTS 是硬阈值（拒绝）。
    if len(path) > HARD_MAX_PATH_POINTS:
        errors.append(f"path exceeds hard limit of {HARD_MAX_PATH_POINTS} points")
        return {"ok": False, "errors": errors, "warnings": warnings}

    max_x = bounds.get("x", DEFAULT_WORKSPACE_MM["x"])
    max_y = bounds.get("y", DEFAULT_WORKSPACE_MM["y"])

    for i, point in enumerate(path):
        if not isinstance(point, dict):
            errors.append(f"point {i} is not an object")
            continue
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            errors.append(f"point {i} missing x or y")
            continue
        # bool 是 int 的子类但坐标语义非法；非数值坐标必须拒绝而非抛 TypeError（500）。
        if not _is_number(x) or not _is_number(y):
            errors.append(f"point {i} has non-numeric x or y")
            continue
        if x < 0 or x > max_x or y < 0 or y > max_y:
            errors.append(f"point {i} out of workspace bounds")

    if len(path) > MAX_PATH_POINTS:
        warnings.append(f"path exceeds {MAX_PATH_POINTS} points")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
