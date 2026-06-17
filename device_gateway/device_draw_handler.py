"""设备绘图路由 - device_draw 模式"""

import logging
from typing import Dict, Any, Optional
from dashscope_image_client import DashScopeImageClient
from xiaozhi_drawing.svg_converter import SVGConverter
from xiaozhi_drawing.svg_validator import validate_svg_path
from xiaozhi_drawing.path_optimizer import optimize_svg_path
from xiaozhi_drawing.preset_shapes import get_preset_svg

from device_gateway.draw_prompt_enhancer import enhance_drawing_prompt

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


async def _generate_image(prompt: str, model: str, size: str) -> Dict[str, Any]:
    """Enhance prompt and generate an image via DashScope."""
    enhanced_prompt = enhance_drawing_prompt(prompt)
    logger.info(f"Enhanced prompt: {enhanced_prompt[:100]}...")
    client = DashScopeImageClient()
    return client.generate(prompt=enhanced_prompt, model=model, size=size, n=1)


async def _convert_and_optimize(
    image_url: str,
    model: str,
) -> Dict[str, Any]:
    """Convert image to SVG, validate, optimize and return the final payload."""
    converter = SVGConverter()
    svg_result = await converter.convert_url_to_svg(image_url)

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

    optimization = optimize_svg_path(svg_path, tolerance=2.0, target_size=(180, 180))
    logger.info(
        f"Path optimized: {optimization.original_points} -> "
        f"{optimization.optimized_points} points ({optimization.reduction_ratio:.1%} reduction)"
    )
    return _build_success_response(image_url, svg_result, optimization, model)


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

    logger.info(f"Device {device_id} draw request: {prompt[:50]}... (model={model})")

    preset = _try_preset_shape(prompt)
    if preset:
        return preset

    try:
        result = await _generate_image(prompt, model, size)
        if result["status"] != "success" or not result["images"]:
            return _build_failed_response(model, result.get("error", "Unknown error"))

        image_url = result["images"][0]["url"]
        return await _convert_and_optimize(image_url, model)
    except Exception as e:
        logger.error(f"Device draw failed: {e}")
        return _build_failed_response(model, str(e))
