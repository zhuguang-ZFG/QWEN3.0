"""设备写字路由 - device_write 模式（确定性，无 LLM）"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


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
            'path_data': str,  # SVG 路径数据
            'model': 'deterministic',
            'error': str | None
        }
    """
    logger.info(f"Device {device_id} write request: {text[:30]}... (font={font_style}, size={size})")

    try:
        # TODO: 实现字体路径生成
        # 1. 从字体库加载字体轮廓
        # 2. 生成 SVG 路径
        # 3. 应用尺寸和间距

        # 临时返回占位符
        path_data = "M 0 0 L 100 0 L 100 100 L 0 100 Z"  # 占位符矩形

        return {
            'status': 'success',
            'path_data': path_data,
            'model': 'deterministic',
            'error': None
        }

    except Exception as e:
        logger.error(f"Device write failed: {e}")
        return {
            'status': 'failed',
            'path_data': '',
            'model': 'deterministic',
            'error': str(e)
        }
