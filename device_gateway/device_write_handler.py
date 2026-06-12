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
        # 获取字体参数
        font_params = FONT_STYLES.get(font_style, FONT_STYLES['default'])
        size_params = FONT_SIZES.get(size, FONT_SIZES['medium'])

        # 计算缩放因子
        scale = font_params['scale'] * size_params['scale']

        # 生成路径（返回点列表）
        path_list = text_to_path(
            text,
            origin_x=5.0,
            origin_y=20.0,
            scale=scale
        )

        # 计算边界
        if path_list:
            min_x = min(p['x'] for p in path_list)
            max_x = max(p['x'] for p in path_list)
            min_y = min(p['y'] for p in path_list)
            max_y = max(p['y'] for p in path_list)
            width = int(max_x - min_x) + 20  # 添加边距
            height = int(max_y - min_y) + 20
        else:
            width = 100
            height = 50

        # 生成预览 SVG
        svg_preview = preview_svg(path_list, width, height)

        return {
            'status': 'success',
            'path_data': path_list,
            'preview_svg': svg_preview,
            'width': width,
            'height': height,
            'model': 'deterministic',
            'error': None
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
