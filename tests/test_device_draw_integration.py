"""端到端测试 - device_draw 集成验证"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from device_gateway.device_draw_handler import handle_device_draw


@pytest.mark.asyncio
async def test_device_draw_preset_shape():
    """测试预设图形快速路径（无 API 调用）"""
    result = await handle_device_draw("画一个圆形", device_id="test-preset")

    # 验证预设图形
    assert result['status'] == 'success'
    assert result['svg_path'] is not None
    assert 'A' in result['svg_path']  # 圆弧指令
    assert result['model'] == 'preset:circle'
    assert result.get('preset') is True
    assert result['image_url'] == ''  # 无图片 URL


@pytest.mark.asyncio
async def test_device_draw_with_validation_and_optimization():
    """测试完整流程：生成→转换→验证→优化"""

    # Mock DashScope 客户端
    mock_client = MagicMock()
    mock_client.generate.return_value = {
        'status': 'success',
        'images': [{'url': 'http://example.com/image.jpg'}]
    }

    # Mock SVG 转换器
    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(return_value={
        'status': 'success',
        'svg_path': 'M 10 10 L 50 50 L 90 10 Z',
        'width': 512,
        'height': 512
    })

    with patch('device_gateway.device_draw_handler.DashScopeImageClient', return_value=mock_client), \
         patch('device_gateway.device_draw_handler.SVGConverter', return_value=mock_converter):

        result = await handle_device_draw("画一只猫", device_id="test-001")

        # 验证结果
        assert result['status'] == 'success'
        assert result['image_url'] == 'http://example.com/image.jpg'
        assert result['svg_path'] is not None
        assert result['svg_path'].startswith('M')
        assert result['svg_path'].endswith('Z')
        assert 'optimization' in result
        assert result['optimization']['optimized_points'] > 0


@pytest.mark.asyncio
async def test_device_draw_validation_failure():
    """测试 SVG 验证失败"""

    mock_client = MagicMock()
    mock_client.generate.return_value = {
        'status': 'success',
        'images': [{'url': 'http://example.com/image.jpg'}]
    }

    # 返回超出工作区的路径
    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(return_value={
        'status': 'success',
        'svg_path': 'M 0 0 L 500 500 Z',  # 超出 200x200
        'width': 512,
        'height': 512
    })

    with patch('device_gateway.device_draw_handler.DashScopeImageClient', return_value=mock_client), \
         patch('device_gateway.device_draw_handler.SVGConverter', return_value=mock_converter):

        result = await handle_device_draw("画一只猫", device_id="test-002")

        # 应该返回 partial 状态
        assert result['status'] == 'partial'
        assert result['svg_path'] is None
        assert 'validation failed' in result['error']


@pytest.mark.asyncio
async def test_device_draw_optimization_reduces_points():
    """测试路径优化减少点数"""

    mock_client = MagicMock()
    mock_client.generate.return_value = {
        'status': 'success',
        'images': [{'url': 'http://example.com/image.jpg'}]
    }

    # 高密度路径
    points = " ".join(f"L {i} {i}" for i in range(50))
    mock_converter = MagicMock()
    mock_converter.convert_url_to_svg = AsyncMock(return_value={
        'status': 'success',
        'svg_path': f'M 0 0 {points} Z',
        'width': 512,
        'height': 512
    })

    with patch('device_gateway.device_draw_handler.DashScopeImageClient', return_value=mock_client), \
         patch('device_gateway.device_draw_handler.SVGConverter', return_value=mock_converter):

        result = await handle_device_draw("画线条", device_id="test-003")

        assert result['status'] == 'success'
        opt = result['optimization']
        assert opt['optimized_points'] < opt['original_points']
        assert opt['reduction_ratio'] > 0
