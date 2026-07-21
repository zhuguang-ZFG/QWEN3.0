"""SVG validate/optimize targets follow device workspace (not fixed 200/180)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from device_gateway.path_workspace import resolve_workspace_mm
from xiaozhi_drawing.path_optimizer import optimize_svg_path
from xiaozhi_drawing.svg_validator import validate_svg_path

_log = logging.getLogger(__name__)


def workspace_target_px(device_id: Optional[str] = None) -> tuple[float, float]:
    """Map device workspace mm to SVG target with ~10% margin for precheck."""
    ws = resolve_workspace_mm(device_id=device_id)
    return max(float(ws["x"]) * 0.9, 1.0), max(float(ws["y"]) * 0.9, 1.0)


def validate_draw_svg(svg_result: dict[str, Any], *, device_id: Optional[str] = None) -> tuple[Any, str]:
    w, h = workspace_target_px(device_id)
    validation = validate_svg_path(svg_result["svg_path"], workspace=(w, h))
    if not validation.valid:
        _log.warning("SVG validation failed: %s", validation.errors)
        return validation, f"SVG validation failed: {', '.join(validation.errors)}"
    return validation, ""


def optimize_draw_svg(svg_path: Any, svg_result: dict[str, Any], *, device_id: Optional[str] = None) -> Any:
    w, h = workspace_target_px(device_id)
    optimization = optimize_svg_path(
        svg_path,
        tolerance=2.0,
        target_size=(w, h),
        close=not svg_result.get("skeleton_applied", False),
    )
    if svg_result.get("skeleton_applied"):
        _log.info("Skeleton SVG optimized as open strokes (method=%s)", svg_result.get("thinning_method"))
    _log.info(
        "Path optimized: %s -> %s points (%.1f%% reduction) target=%.0fx%.0f",
        optimization.original_points,
        optimization.optimized_points,
        optimization.reduction_ratio * 100,
        w,
        h,
    )
    return optimization
