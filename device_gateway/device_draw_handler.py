"""设备绘图路由 - device_draw 模式"""

import logging
from typing import Dict, Any, Optional
from dashscope_image_client import DashScopeImageClient
from device_gateway.handwriting_path import try_text_to_handwriting
from device_gateway.image_fallback import generate_via_image_fallback
from xiaozhi_drawing.svg_converter import SVGConverter
from xiaozhi_drawing.svg_validator import validate_svg_path
from xiaozhi_drawing.path_optimizer import optimize_svg_path
from xiaozhi_drawing.preset_shapes import get_preset_svg

from device_gateway.device_profile.registry import get_device_profile
from device_gateway.draw_prompt_enhancer import (
    enhance_drawing_prompt,
    record_device_draw_turn,
    record_failed_draw_prompt,
    screen_drawing_request,
)
from device_gateway.path_pipeline import precheck_draw_motion_path
from device_gateway.draw_responses import build_failed_response as _build_failed_response
from device_gateway.draw_responses import build_partial_response as _build_partial_response
from device_gateway.draw_responses import build_success_response as _build_success_response

logger = logging.getLogger(__name__)

PRESET_KEYWORDS = {
    "circle": ["圆", "圆形", "circle"],
    "square": ["方", "方形", "正方形", "square"],
    "triangle": ["三角", "三角形", "triangle"],
    "star": ["星", "星星", "五角星", "star"],
    "heart": ["心", "心形", "heart", "爱心"],
    "crescent": ["月", "月亮", "月牙", "crescent"],
}


def _try_preset_shape(prompt: str) -> Optional[Dict[str, Any]]:
    """Detect preset shape keywords and return its SVG if matched."""
    for shape, keywords in PRESET_KEYWORDS.items():
        if any(kw in prompt.lower() for kw in keywords):
            logger.info(f"Detected preset shape: {shape}")
            result = get_preset_svg(shape, size=180)
            if result["status"] == "success":
                err = precheck_draw_motion_path(result["svg_path"])
                if err:
                    logger.warning("Preset motion bounds precheck failed: %s", err)
                    return _build_failed_response(f"preset:{shape}", f"Motion bounds precheck failed: {err}")
                return {
                    "status": "success",
                    "image_url": "",
                    "svg_path": result["svg_path"],
                    "width": result["width"],
                    "height": result["height"],
                    "model": f"preset:{shape}",
                    "error": None,
                    "preset": True,
                }
    return None


async def _generate_image(
    prompt: str,
    model: str,
    size: str,
    *,
    device_type: str = "esp32_xy_plotter",
    style: str = "简约",
    complexity: str = "中",
    previous_failed_prompts: list[str] | None = None,
    conversation_context: str = "",
    device_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Enhance prompt and generate an image via DashScope, with multi-backend fallback."""
    device_profile = get_device_profile(device_id) if device_id else None
    enhanced_prompt = enhance_drawing_prompt(
        prompt,
        style=style,
        complexity=complexity,
        device_type=device_type,
        previous_failed_prompts=previous_failed_prompts,
        conversation_context=conversation_context,
        device_profile=device_profile,
    )
    logger.info(f"Enhanced prompt: {enhanced_prompt[:100]}...")
    client = DashScopeImageClient()
    result = client.generate(prompt=enhanced_prompt, model=model, size=size, n=1)
    # DashScope 失败时降级到 /v1/images 多后端链路，消除单点风险
    if result.get("status") != "success" or not result.get("images"):
        logger.info(f"DashScope failed for device {device_id}, trying image fallback")
        fallback = await generate_via_image_fallback(enhanced_prompt, size, device_id)
        if fallback.get("status") == "success":
            return fallback
    return result


async def _convert_image_to_svg(image_url: str) -> Dict[str, Any]:
    """Convert an image URL to an SVG result dict."""
    converter = SVGConverter()
    return await converter.convert_url_to_svg(image_url, skeletonize=True, reorder_strokes=True)


def _validate_svg(svg_result: Dict[str, Any]) -> tuple[Any, str]:
    """Validate SVG path and return (validation, error_message)."""
    svg_path = svg_result["svg_path"]
    validation = validate_svg_path(svg_path, workspace=(200, 200))
    if not validation.valid:
        logger.warning("SVG validation failed: %s", validation.errors)
        return validation, f"SVG validation failed: {', '.join(validation.errors)}"
    return validation, ""


def _optimize_svg_path(svg_path: Any, svg_result: Dict[str, Any]) -> Any:
    """Optimize SVG path and log statistics."""
    optimization = optimize_svg_path(
        svg_path,
        tolerance=2.0,
        target_size=(180, 180),
        close=not svg_result.get("skeleton_applied", False),
    )
    if svg_result.get("skeleton_applied"):
        logger.info("Skeleton SVG optimized as open strokes (method=%s)", svg_result.get("thinning_method"))
    logger.info(
        "Path optimized: %s -> %s points (%.1f%% reduction)",
        optimization.original_points,
        optimization.optimized_points,
        optimization.reduction_ratio * 100,
    )
    return optimization


def _check_motion_bounds(optimization: Any) -> str | None:
    """Return an error string if the optimized path exceeds motion bounds."""
    bounds_err = precheck_draw_motion_path(optimization.optimized_path)
    if bounds_err:
        logger.warning("Draw motion bounds precheck failed: %s", bounds_err)
    return bounds_err


async def _convert_and_optimize(
    image_url: str,
    model: str,
) -> Dict[str, Any]:
    """Convert image to SVG, validate, optimize and return the final payload."""
    svg_result = await _convert_image_to_svg(image_url)
    if svg_result["status"] != "success":
        return _build_partial_response(image_url, 0, 0, model, error=f"SVG conversion failed: {svg_result['error']}")

    validation, error = _validate_svg(svg_result)
    if error:
        return _build_partial_response(image_url, svg_result["width"], svg_result["height"], model, error=error)

    optimization = _optimize_svg_path(svg_result["svg_path"], svg_result)
    bounds_err = _check_motion_bounds(optimization)
    if bounds_err:
        return _build_partial_response(
            image_url,
            svg_result["width"],
            svg_result["height"],
            model,
            error=f"Motion bounds precheck failed: {bounds_err}",
        )
    return _build_success_response(image_url, svg_result, optimization, model)


def _finalize_draw_response(
    device_id: Optional[str],
    prompt: str,
    response: Dict[str, Any],
) -> Dict[str, Any]:
    """Record draw turn in session memory before returning."""
    status = str(response.get("status") or "failed")
    record_device_draw_turn(
        device_id,
        prompt,
        status=status,
        error=str(response.get("error") or ""),
    )
    return response


from device_gateway.device_draw_config import _resolve_draw_request  # noqa: F401


async def _convert_provided_image(image_url: str, config: dict, device_id: str | None, prompt: str) -> dict[str, Any]:
    """Convert a caller-provided image URL to an optimized draw path."""
    try:
        response = await _convert_and_optimize(image_url, config["model"])
        if response.get("status") != "success":
            record_failed_draw_prompt(device_id, prompt, error=str(response.get("error") or ""))
        return _finalize_draw_response(device_id, prompt, response)
    except Exception as exc:
        logger.error("Device draw failed for provided image: %s", exc)
        record_failed_draw_prompt(device_id, prompt, error=str(exc))
        return _finalize_draw_response(device_id, prompt, _build_failed_response(config["model"], str(exc)))


def _try_fast_paths(
    prompt: str,
    device_id: str | None,
    device_type: str | None,
    font_name: str | None = None,
) -> dict[str, Any] | None:
    """Try preset shape then handwriting font path; return first match or None."""
    return _try_preset_shape(prompt) or try_text_to_handwriting(prompt, device_id, device_type, font_name=font_name)


async def _try_preset_or_generate(
    prompt: str, device_id: str | None, config: dict, image_url: str | None
) -> dict[str, Any]:
    """Try provided image URL, then preset shape/handwriting fast paths, then AI generation."""
    if image_url and len(image_url) < 2000 and image_url.startswith(("https://", "http://")):
        return await _convert_provided_image(image_url, config, device_id, prompt)
    fast = _try_fast_paths(prompt, device_id, config.get("device_type"), config.get("font_name"))
    if fast:
        if fast.get("status") != "success":
            record_failed_draw_prompt(device_id, prompt, error=str(fast.get("error") or ""))
        return _finalize_draw_response(device_id, prompt, fast)

    screen = screen_drawing_request(prompt, device_id)
    if not screen["feasible"]:
        record_failed_draw_prompt(device_id, prompt, error=screen["reason"])
        return _finalize_draw_response(
            device_id,
            prompt,
            _build_failed_response(config["model"], screen["suggestion"]),
        )

    try:
        result = await _generate_image(
            screen["simplified_prompt"],
            config["model"],
            config["size"],
            device_type=config["device_type"],
            style=config["style"],
            complexity=config["complexity"],
            previous_failed_prompts=config.get("failed_prompts") or None,
            conversation_context=config.get("conversation_context") or "",
            device_id=device_id,
        )
        if result["status"] != "success" or not result["images"]:
            record_failed_draw_prompt(device_id, prompt, error=str(result.get("error") or "Unknown error"))
            return _finalize_draw_response(
                device_id,
                prompt,
                _build_failed_response(config["model"], result.get("error", "Unknown error")),
            )

        generated_image_url = result["images"][0]["url"]
        response = await _convert_and_optimize(generated_image_url, config["model"])
        if response.get("status") != "success":
            record_failed_draw_prompt(device_id, prompt, error=str(response.get("error") or ""))
        return _finalize_draw_response(device_id, prompt, response)
    except Exception as e:
        logger.error(f"Device draw failed: {e}")
        record_failed_draw_prompt(device_id, prompt, error=str(e))
        return _finalize_draw_response(device_id, prompt, _build_failed_response(config["model"], str(e)))


async def handle_device_draw(
    prompt: str,
    device_id: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Handle a device drawing request.

    Uses a caller-provided image URL when available; otherwise tries preset
    shape matching and falls back to AI image generation via DashScope, then
    SVG conversion and optimization.
    """
    prefs = user_preferences or {}
    config = _resolve_draw_request(prefs, device_id, prompt)
    return await _try_preset_or_generate(prompt, device_id, config, image_url)
