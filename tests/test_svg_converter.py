"""测试 SVG 转换器"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO
from xiaozhi_drawing.svg_converter import SVGConverter


@pytest.mark.asyncio
async def test_convert_url_to_svg_success():
    """测试 URL 转 SVG 成功"""
    # 创建 1x1 红色 PNG
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    mock_response = MagicMock()
    mock_response.content = img_bytes.getvalue()
    mock_response.raise_for_status = MagicMock()

    with patch('xiaozhi_drawing.svg_converter.httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        converter = SVGConverter()
        result = await converter.convert_url_to_svg('https://example.com/image.jpg')

        assert result['status'] == 'success'
        assert result['svg_path']
        assert result['width'] > 0
        assert result['height'] > 0
        assert result['error'] is None


@pytest.mark.asyncio
async def test_convert_url_to_svg_download_failed():
    """测试下载失败"""
    with patch('xiaozhi_drawing.svg_converter.httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=Exception('Network error'))
        mock_client.return_value.__aenter__.return_value = mock_instance

        converter = SVGConverter()
        result = await converter.convert_url_to_svg('https://example.com/image.jpg')

        assert result['status'] == 'failed'
        assert 'error' in result['error'].lower()
