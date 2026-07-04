"""Path validation facade for DLC core."""

from __future__ import annotations

from typing import Any

from dlc_core.safety import DEFAULT_WORKSPACE_MM


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

    max_x = bounds.get("x", DEFAULT_WORKSPACE_MM["x"])
    max_y = bounds.get("y", DEFAULT_WORKSPACE_MM["y"])

    for i, point in enumerate(path):
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            errors.append(f"point {i} missing x or y")
            continue
        if x < 0 or x > max_x or y < 0 or y > max_y:
            errors.append(f"point {i} out of workspace bounds")

    if len(path) > 200:
        warnings.append("path exceeds 200 points")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
