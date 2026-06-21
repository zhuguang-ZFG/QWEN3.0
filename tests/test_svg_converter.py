"""测试 SVG 转换器"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO
from xiaozhi_drawing.svg_converter import SVGConverter


@pytest.mark.asyncio
async def test_convert_url_to_svg_success():
    """测试 URL 转 SVG 成功（OpenCV 矢量化）"""
    # 创建简单的黑白图片（易于轮廓检测）
    from PIL import Image
    import numpy as np

    # 创建一个带黑色圆形的白色图片
    img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2 = __import__("cv2")
    cv2.circle(img_array, (50, 50), 30, (0, 0, 0), -1)
    img = Image.fromarray(img_array)

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    mock_response = MagicMock()
    mock_response.content = img_bytes.getvalue()
    mock_response.raise_for_status = MagicMock()

    with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        converter = SVGConverter()
        result = await converter.convert_url_to_svg("https://example.com/image.jpg")

        assert result["status"] == "success"
        assert result["svg_path"]
        assert result["svg_path"].startswith("M")
        assert "L" in result["svg_path"]
        assert result["width"] > 0
        assert result["height"] > 0
        assert "contour_count" in result
        assert result["error"] is None


@pytest.mark.asyncio
async def test_convert_url_to_svg_skeleton_mode_open_paths():
    """骨架模式端到端：粗线输入应产出无 Z 的开放路径。"""
    pytest.importorskip("cv2")
    from PIL import Image
    import numpy as np

    img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2 = __import__("cv2")
    cv2.line(img_array, (10, 50), (90, 50), (0, 0, 0), 8)
    img = Image.fromarray(img_array)

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    mock_response = MagicMock()
    mock_response.content = img_bytes.getvalue()
    mock_response.raise_for_status = MagicMock()

    with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_instance

        converter = SVGConverter()
        result = await converter.convert_url_to_svg("https://example.com/image.jpg", skeletonize=True)

        assert result["status"] == "success"
        assert result["skeleton_applied"] is True
        assert result["thinning_method"] in {"skimage", "ximgproc", "morphological"}
        assert " Z" not in result["svg_path"]


@pytest.mark.asyncio
async def test_convert_url_to_svg_download_failed():
    """测试下载失败"""
    with patch("xiaozhi_drawing.svg_converter.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value.__aenter__.return_value = mock_instance

        converter = SVGConverter()
        result = await converter.convert_url_to_svg("https://example.com/image.jpg")

        assert result["status"] == "failed"
        assert "error" in result["error"].lower()
