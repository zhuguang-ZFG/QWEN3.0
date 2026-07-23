"""Image URL → SVG path conversion helpers for device_draw."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from xiaozhi_drawing.svg_converter import SVGConverter
from device_gateway.draw_svg_stage import optimize_draw_svg, validate_draw_svg
from device_gateway.path_pipeline import precheck_draw_motion_path
from device_gateway.draw_responses import build_partial_response as _build_partial_response
from device_gateway.draw_responses import build_success_response as _build_success_response

logger = logging.getLogger(__name__)


async def _convert_image_to_svg(
    image_url: str,
    *,
    allowed_hosts: frozenset[str] | None = None,
) -> Dict[str, Any]:
    """Convert an image URL to an SVG result dict."""
    converter = SVGConverter()
    return await converter.convert_url_to_svg(
        image_url,
        skeletonize=True,
        reorder_strokes=True,
        allowed_hosts=allowed_hosts,
    )


def _check_motion_bounds(optimization: Any, *, device_id: Optional[str] = None) -> str | None:
    """Return an error string if the optimized path exceeds motion bounds."""
    bounds_err = precheck_draw_motion_path(optimization.optimized_path, device_id=device_id)
    if bounds_err:
        logger.warning("Draw motion bounds precheck failed: %s", bounds_err)
    return bounds_err


async def _convert_and_optimize(
    image_url: str,
    model: str,
    *,
    device_id: Optional[str] = None,
    allowed_hosts: frozenset[str] | None = None,
) -> Dict[str, Any]:
    """Convert → optimize into workspace → validate/precheck (avoid rejecting raw pixel paths)."""
    svg_result = await _convert_image_to_svg(image_url, allowed_hosts=allowed_hosts)
    if svg_result["status"] != "success":
        return _build_partial_response(image_url, 0, 0, model, error=f"SVG conversion failed: {svg_result['error']}")

    # Optimize first so large image-space paths scale into the device canvas before
    # bbox validation (W1). Then validate + motion precheck on the scaled path.
    optimization = optimize_draw_svg(svg_result["svg_path"], svg_result, device_id=device_id)
    _validation, error = validate_draw_svg(
        {"svg_path": optimization.optimized_path},
        device_id=device_id,
    )
    if error:
        return _build_partial_response(image_url, svg_result["width"], svg_result["height"], model, error=error)

    bounds_err = _check_motion_bounds(optimization, device_id=device_id)
    if bounds_err:
        return _build_partial_response(
            image_url,
            svg_result["width"],
            svg_result["height"],
            model,
            error=f"Motion bounds precheck failed: {bounds_err}",
        )
    return _build_success_response(image_url, svg_result, optimization, model)
