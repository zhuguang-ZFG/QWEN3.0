"""设备写字路由 - device_write 模式（确定性，无 LLM）"""
import logging
from typing import Dict, Any, Optional

from device_gateway.path_pipeline import text_to_path, preview_svg

logger = logging.getLogger(__name__)

# 字体样式映射
FONT_STYLES = {
    'default': {'scale': 1.0, 'spacing': 1.0},
    'handwriting': {'scale': 0.9, 'spacing': 1.2},
    'calligraphy': {'scale': 1.1, 'spacing': 0.9},
}

# 字体大小映射
FONT_SIZES = {
    'small': {'scale': 0.5, 'target_height': 30},
    'medium': {'scale': 1.0, 'target_height': 60},
    'large': {'scale': 1.5, 'target_height': 90},
}


def _resolve_font_params(font_style: str, size: str) -> float:
    """Compute combined scale factor from font style and size."""
    fp = FONT_STYLES.get(font_style, FONT_STYLES['default'])
    sp = FONT_SIZES.get(size, FONT_SIZES['medium'])
    return fp['scale'] * sp['scale']


def _compute_bounds(path_list: list[dict]) -> tuple[int, int]:
    """Compute width/height from path points with margin."""
    if not path_list:
        return 100, 50
    xs = [p['x'] for p in path_list]
    ys = [p['y'] for p in path_list]
    return int(max(xs) - min(xs)) + 20, int(max(ys) - min(ys)) + 20


async def handle_device_write(
    text: str,
    device_id: Optional[str] = None,
    font_style: str = 'default',
    size: str = 'medium'
) -> Dict[str, Any]:
    """
    处理设备写字请求（确定性路径，不调用 LLM）

    Args:
        text: 要写的文字
        device_id: 设备 ID
        font_style: 字体样式 (default, handwriting, calligraphy)
        size: 字体大小 (small, medium, large)

    Returns:
        {
            'status': 'success' | 'failed',
            'path_data': list,  # 路径点列表
            'preview_svg': str,  # 预览 SVG
            'width': int,
            'height': int,
            'model': 'deterministic',
            'error': str | None
        }
    """
    logger.info(f"Device {device_id} write request: {text[:30]}... (font={font_style}, size={size})")
    try:
        scale = _resolve_font_params(font_style, size)
        path_list = text_to_path(text, origin_x=5.0, origin_y=20.0, scale=scale)
        width, height = _compute_bounds(path_list)
        return {
            'status': 'success', 'path_data': path_list,
            'preview_svg': preview_svg(path_list, width, height),
            'width': width, 'height': height, 'model': 'deterministic', 'error': None,
        }

    except Exception as e:
        logger.error(f"Device write failed: {e}")
        return {
            'status': 'failed',
            'path_data': [],
            'preview_svg': '',
            'width': 0,
            'height': 0,
            'model': 'deterministic',
            'error': str(e)
        }
