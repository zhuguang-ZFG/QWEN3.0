"""设备绘图路由 - device_draw 模式"""
import logging
from typing import Dict, Any, Optional
from dashscope_image_client import DashScopeImageClient
from xiaozhi_drawing.svg_converter import SVGConverter

logger = logging.getLogger(__name__)


async def handle_device_draw(
    prompt: str,
    device_id: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None
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
    model = prefs.get('model', 'wanx-v1')
    size = prefs.get('size', '1024*1024')

    logger.info(f"Device {device_id} draw request: {prompt[:50]}... (model={model})")

    try:
        # 1. 生成图片
        client = DashScopeImageClient()
        result = client.generate(prompt=prompt, model=model, size=size, n=1)

        if result['status'] != 'success' or not result['images']:
            return {
                'status': 'failed',
                'image_url': '',
                'svg_path': None,
                'width': 0,
                'height': 0,
                'model': model,
                'error': result.get('error', 'Unknown error')
            }

        image_url = result['images'][0]['url']

        # 2. 转换为 SVG
        converter = SVGConverter()
        svg_result = await converter.convert_url_to_svg(image_url)

        if svg_result['status'] == 'success':
            return {
                'status': 'success',
                'image_url': image_url,
                'svg_path': svg_result['svg_path'],
                'width': svg_result['width'],
                'height': svg_result['height'],
                'model': model,
                'error': None
            }
        else:
            return {
                'status': 'partial',
                'image_url': image_url,
                'svg_path': None,
                'width': 0,
                'height': 0,
                'model': model,
                'error': f"SVG conversion failed: {svg_result['error']}"
            }

    except Exception as e:
        logger.error(f"Device draw failed: {e}")
        return {
            'status': 'failed',
            'image_url': '',
            'svg_path': None,
            'width': 0,
            'height': 0,
            'model': model,
            'error': str(e)
        }
