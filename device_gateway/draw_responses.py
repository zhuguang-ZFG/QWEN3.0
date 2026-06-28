"""Response payload builders for device draw handler."""

from __future__ import annotations

from typing import Any, Dict

# 对外统一品牌名，隐藏真实生图模型（wanx2.1-t2i-turbo 等）。
# 真实模型名仅用于内部日志（device_draw_handler），响应体对外统一返回品牌标签。
PUBLIC_DRAW_MODEL_LABEL = "LiMa 生图"


def build_failed_response(model: str, error: str) -> Dict[str, Any]:
    """Build a failed draw response payload."""
    return {
        "status": "failed",
        "image_url": "",
        "svg_path": None,
        "width": 0,
        "height": 0,
        "model": PUBLIC_DRAW_MODEL_LABEL,
        "error": error,
    }


def build_partial_response(
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
        "model": PUBLIC_DRAW_MODEL_LABEL,
        "error": error,
    }


def build_success_response(
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
        "model": PUBLIC_DRAW_MODEL_LABEL,
        "error": None,
        "optimization": {
            "original_points": optimization.original_points,
            "optimized_points": optimization.optimized_points,
            "reduction_ratio": optimization.reduction_ratio,
        },
    }
