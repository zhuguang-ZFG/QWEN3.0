"""设备绘图路由 - device_draw 模式"""

import logging
from typing import Dict, Any, Optional
from dashscope_image_client import DashScopeImageClient
from xiaozhi_drawing.svg_converter import SVGConverter
from xiaozhi_drawing.svg_validator import validate_svg_path
from xiaozhi_drawing.path_optimizer import optimize_svg_path
from xiaozhi_drawing.preset_shapes import get_preset_svg

from device_gateway.draw_prompt_enhancer import enhance_drawing_prompt
from device_gateway.draw_prompt_context import (
    get_draw_conversation_context,
    get_failed_draw_prompts,
    record_device_draw_turn,
    record_failed_draw_prompt,
    resolve_device_type,
)
from device_gateway.draw_path_bounds import precheck_draw_motion_path

logger = logging.getLogger(__name__)

# 预设图形关键词
PRESET_KEYWORDS = {
    "circle": ["圆", "圆形", "circle"],
    "square": ["方", "方形", "正方形", "square"],
    "triangle": ["三角", "三角形", "triangle"],
    "star": ["星", "星星", "五角星", "star"],
    "heart": ["心", "心形", "heart", "爱心"],
    "crescent": ["月", "月亮", "月牙", "crescent"],
}


def _build_failed_response(model: str, error: str) -> Dict[str, Any]:
    """Build a failed draw response payload."""
    return {
        "status": "failed",
        "image_url": "",
        "svg_path": None,
        "width": 0,
        "height": 0,
        "model": model,
        "error": error,
    }


def _build_partial_response(
    image_url: str,
    width: int,
    height: int,
    model: str,
    error: str,
) -> Dict[str, Any]:
    """Build a partial draw response payload."""
    return {
        "status": "partial",
        "image_url": image_url,
        "svg_path": None,
        "width": width,
        "height": height,
        "model": model,
        "error": error,
    }


def _build_success_response(
    image_url: str,
    svg_result: Dict[str, Any],
    optimization: Any,
    model: str,
) -> Dict[str, Any]:
    """Build a successful draw response payload."""
    return {
        "status": "success",
        "image_url": image_url,
        "svg_path": optimization.optimized_path,
        "width": svg_result["width"],
        "height": svg_result["height"],
        "model": model,
        "error": None,
        "optimization": {
            "original_points": optimization.original_points,
            "optimized_points": optimization.optimized_points,
            "reduction_ratio": optimization.reduction_ratio,
        },
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
) -> Dict[str, Any]:
    """Enhance prompt and generate an image via DashScope."""
    enhanced_prompt = enhance_drawing_prompt(
        prompt,
        style=style,
        complexity=complexity,
        device_type=device_type,
        previous_failed_prompts=previous_failed_prompts,
        conversation_context=conversation_context,
    )
    logger.info(f"Enhanced prompt: {enhanced_prompt[:100]}...")
    client = DashScopeImageClient()
    return client.generate(prompt=enhanced_prompt, model=model, size=size, n=1)


async def _convert_and_optimize(
    image_url: str,
    model: str,
) -> Dict[str, Any]:
    """Convert image to SVG, validate, optimize and return the final payload."""
    converter = SVGConverter()
    svg_result = await converter.convert_url_to_svg(image_url, skeletonize=True)

    if svg_result["status"] != "success":
        return _build_partial_response(
            image_url,
            0,
            0,
            model,
            error=f"SVG conversion failed: {svg_result['error']}",
        )

    svg_path = svg_result["svg_path"]
    validation = validate_svg_path(svg_path, workspace=(200, 200))
    if not validation.valid:
        logger.warning(f"SVG validation failed: {validation.errors}")
        return _build_partial_response(
            image_url,
            svg_result["width"],
            svg_result["height"],
            model,
            error=f"SVG validation failed: {', '.join(validation.errors)}",
        )

    optimization = optimize_svg_path(
        svg_path,
        tolerance=2.0,
        target_size=(180, 180),
        close=not svg_result.get("skeleton_applied", False),
    )
    if svg_result.get("skeleton_applied"):
        logger.info("Skeleton SVG optimized as open strokes (method=%s)", svg_result.get("thinning_method"))
    logger.info(
        f"Path optimized: {optimization.original_points} -> "
        f"{optimization.optimized_points} points ({optimization.reduction_ratio:.1%} reduction)"
    )
    bounds_err = precheck_draw_motion_path(optimization.optimized_path)
    if bounds_err:
        logger.warning("Draw motion bounds precheck failed: %s", bounds_err)
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


async def handle_device_draw(
    prompt: str, device_id: Optional[str] = None, user_preferences: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    处理设备绘图请求

    Args:
        prompt: 用户绘图描述
        device_id: 设备 ID
        user_preferences: 用户偏好（模型、尺寸等）

    Returns:
        {
            'status': 'success' | 'failed',
            'image_url': str,
            'svg_path': str | None,
            'width': int,
            'height': int,
            'model': str,
            'error': str | None
        }
    """
    prefs = user_preferences or {}
    # wanx-v1 is deprecated/ unavailable; use the current working model.
    model = prefs.get("model", "wanx2.1-t2i-turbo")
    size = prefs.get("size", "1024*1024")
    device_type = resolve_device_type(device_id, prefs)
    style = str(prefs.get("style", "简约"))
    complexity = str(prefs.get("complexity", "中"))
    failed_prompts = get_failed_draw_prompts(device_id)
    conversation_context = get_draw_conversation_context(device_id, prompt)

    logger.info(
        f"Device {device_id} draw request: {prompt[:50]}... "
        f"(model={model}, device_type={device_type}, context_turns={conversation_context.count(chr(10))})"
    )

    preset = _try_preset_shape(prompt)
    if preset:
        if preset.get("status") != "success":
            record_failed_draw_prompt(device_id, prompt, error=str(preset.get("error") or ""))
        return _finalize_draw_response(device_id, prompt, preset)

    try:
        result = await _generate_image(
            prompt,
            model,
            size,
            device_type=device_type,
            style=style,
            complexity=complexity,
            previous_failed_prompts=failed_prompts or None,
            conversation_context=conversation_context,
        )
        if result["status"] != "success" or not result["images"]:
            record_failed_draw_prompt(device_id, prompt, error=str(result.get("error") or "Unknown error"))
            return _finalize_draw_response(
                device_id,
                prompt,
                _build_failed_response(model, result.get("error", "Unknown error")),
            )

        image_url = result["images"][0]["url"]
        response = await _convert_and_optimize(image_url, model)
        if response.get("status") != "success":
            record_failed_draw_prompt(device_id, prompt, error=str(response.get("error") or ""))
        return _finalize_draw_response(device_id, prompt, response)
    except Exception as e:
        logger.error(f"Device draw failed: {e}")
        record_failed_draw_prompt(device_id, prompt, error=str(e))
        return _finalize_draw_response(device_id, prompt, _build_failed_response(model, str(e)))
