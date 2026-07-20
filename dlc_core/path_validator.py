"""Path validation facade for DLC core."""

from __future__ import annotations

import math
from typing import Any

from dlc_core.safety import DEFAULT_WORKSPACE_MM, MAX_PATH_POINTS

# 硬点数上限：超过即拒绝（防畸形/恶意超大 path）。MAX_PATH_POINTS（200）是软阈值（warning）。
HARD_MAX_PATH_POINTS = 5000


def _is_number(value: Any) -> bool:
    """坐标必须是真数值：int/float 但排除 bool（bool 是 int 子类但语义非法）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _workspace_bound_errors(bounds: dict[str, Any]) -> list[str]:
    """CORE-O4：workspace 上界必须是有限正数。

    NaN/Inf 与所有比较返回 False（IEEE 754），会让任意坐标"通过"边界检查；
    负/零工作区没有物理意义。三者都必须显式拒绝而非静默放行。
    """
    errors: list[str] = []
    for axis in ("x", "y", "z"):
        value = bounds.get(axis, DEFAULT_WORKSPACE_MM[axis])
        if not _is_number(value) or value <= 0:
            errors.append(f"workspace bound {axis} must be a finite positive number")
    return errors


def _point_errors(i: int, point: Any, max_x: float, max_y: float, max_z: float) -> list[str]:
    """Validate a single path point against the (pre-validated) bounds."""
    if not isinstance(point, dict):
        return [f"point {i} is not an object"]
    errors: list[str] = []
    x = point.get("x")
    y = point.get("y")
    if x is None or y is None:
        return [f"point {i} missing x or y"]
    # bool 是 int 的子类但坐标语义非法；非数值坐标必须拒绝而非抛 TypeError（500）。
    if not _is_number(x) or not _is_number(y):
        return [f"point {i} has non-numeric x or y"]
    if x < 0 or x > max_x or y < 0 or y > max_y:
        errors.append(f"point {i} out of workspace bounds")
    # Z 可选（缺省 0），但给了就必须是有效数值且在行程内——笔轴超程会压穿纸面/撞机。
    z = point.get("z", 0)
    if not _is_number(z):
        errors.append(f"point {i} has non-numeric z")
    elif z < 0 or z > max_z:
        errors.append(f"point {i} z out of workspace bounds")
    return errors


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

    # CORE-O4：NaN/Inf/非正 workspace 上界会让整条 path 绕过边界校验，必须先拒绝。
    bound_errors = _workspace_bound_errors(bounds)
    if bound_errors:
        errors.extend(bound_errors)
        return {"ok": False, "errors": errors, "warnings": warnings}

    max_x = bounds.get("x", DEFAULT_WORKSPACE_MM["x"])
    max_y = bounds.get("y", DEFAULT_WORKSPACE_MM["y"])
    max_z = bounds.get("z", DEFAULT_WORKSPACE_MM["z"])

    for i, point in enumerate(path):
        errors.extend(_point_errors(i, point, max_x, max_y, max_z))

    if len(path) > MAX_PATH_POINTS:
        warnings.append(f"path exceeds {MAX_PATH_POINTS} points")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
