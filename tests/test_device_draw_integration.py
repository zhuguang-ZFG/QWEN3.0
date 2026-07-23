"""端到端测试 - device_draw 集成验证"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from device_gateway.device_draw_handler import handle_device_draw


@pytest.mark.asyncio
async def test_device_draw_preset_shape():
    """测试预设图形快速路径（无 API 调用）"""
    result = await handle_device_draw("画一个圆形", device_id="test-preset")

    # 验证预设图形
    assert result["status"] == "success"
    assert result["svg_path"] is not None
    assert "A" in result["svg_path"]  # 圆弧指令
    assert result["model"] == "preset:circle"
    assert result.get("preset") is True
    assert result["image_url"] == ""  # 无图片 URL


@pytest.mark.asyncio
async def test_device_draw_with_validation_and_optimization():
    """测试完整流程：生成→转换→验证→优化"""

    # Mock DashScope 客户端
    mock_client = MagicMock()
    mock_client.generate.return_value = {"status": "success", "images": [{"url": "http://example.com/image.jpg"}]}

    # Mock SVG 转换器
    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(
        return_value={"status": "success", "svg_path": "M 10 10 L 50 50 L 90 10 Z", "width": 512, "height": 512}
    )

    with (
        patch("device_gateway.device_draw_handler.DashScopeImageClient", return_value=mock_client),
        patch("device_gateway.draw_image_conversion.SVGConverter", return_value=mock_converter),
    ):
        result = await handle_device_draw("画一只猫", device_id="test-001")

        # 验证结果
        assert result["status"] == "success"
        assert result["image_url"] == "http://example.com/image.jpg"
        assert result["svg_path"] is not None
        assert result["svg_path"].startswith("M")
        assert result["svg_path"].endswith("Z")
        assert "optimization" in result
        assert result["optimization"]["optimized_points"] > 0


@pytest.mark.asyncio
async def test_device_draw_validation_failure():
    """SVG 转换失败应返回 partial 状态。

    大幅图象空间路径现在由 optimize_draw_svg 先缩放进设备画布再验证，
    故「超出工作区」已不再触发拒绝（参见 _convert_and_optimize 注释）。
    本测试改为覆盖转换失败这一稳定 partial 路径。
    """

    mock_client = MagicMock()
    mock_client.generate.return_value = {"status": "success", "images": [{"url": "http://example.com/image.jpg"}]}

    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(
        return_value={
            "status": "failed",
            "error": "skeletonize returned no contours",
            "svg_path": "",
            "width": 0,
            "height": 0,
        }
    )

    with (
        patch("device_gateway.device_draw_handler.DashScopeImageClient", return_value=mock_client),
        patch("device_gateway.draw_image_conversion.SVGConverter", return_value=mock_converter),
    ):
        result = await handle_device_draw("画一只猫", device_id="test-002")

        # 转换失败 → partial
        assert result["status"] == "partial"
        assert result["svg_path"] is None
        assert "SVG conversion failed" in result["error"]


@pytest.mark.asyncio
async def test_device_draw_optimization_reduces_points():
    """测试路径优化减少点数"""

    mock_client = MagicMock()
    mock_client.generate.return_value = {"status": "success", "images": [{"url": "http://example.com/image.jpg"}]}

    # 高密度路径
    points = " ".join(f"L {i} {i}" for i in range(50))
    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(
        return_value={"status": "success", "svg_path": f"M 0 0 {points} Z", "width": 512, "height": 512}
    )

    with (
        patch("device_gateway.device_draw_handler.DashScopeImageClient", return_value=mock_client),
        patch("device_gateway.draw_image_conversion.SVGConverter", return_value=mock_converter),
    ):
        result = await handle_device_draw("画线条", device_id="test-003")

        assert result["status"] == "success"
        opt = result["optimization"]
        assert opt["optimized_points"] < opt["original_points"]
        assert opt["reduction_ratio"] > 0


@pytest.mark.asyncio
async def test_complex_prompt_degrades_to_generation_not_rejected():
    """复杂请求应降级为简化 prompt 送生成，而非在 prompt 层硬拒绝。

    降级优于拒绝：复杂描述简化成单线简笔画尽力画，下游 motion bounds +
    path_validator 硬点数上限兜底。let voice draw anything。
    """
    captured = {}

    mock_client = MagicMock()

    def _capture_generate(*, prompt, model, size, n):
        captured["prompt"] = prompt
        return {"status": "success", "images": [{"url": "http://example.com/x.jpg"}]}

    mock_client.generate.side_effect = _capture_generate

    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(
        return_value={"status": "success", "svg_path": "M 10 10 L 50 50 Z", "width": 200, "height": 200}
    )

    with (
        patch("device_gateway.device_draw_handler.DashScopeImageClient", return_value=mock_client),
        patch("device_gateway.draw_image_conversion.SVGConverter", return_value=mock_converter),
    ):
        # complex 请求（含"城市/人群"高信号词），无 profile 设备
        result = await handle_device_draw("画一座城市和人群的照片", device_id="test-complex")

    # 不应被硬拒绝：应真正走到 DashScope 生成
    assert captured.get("prompt"), "复杂请求应送去生成，而非在 prompt 层拒绝"
    # 送去的应是增强后的简化 prompt（含黑白线条约束）
    assert "黑白" in captured["prompt"] or "线条" in captured["prompt"]
    assert result["status"] == "success"
