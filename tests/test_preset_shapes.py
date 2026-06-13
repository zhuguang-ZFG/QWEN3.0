"""Tests for preset_shapes.py"""
from xiaozhi_drawing.preset_shapes import get_preset_svg


def test_get_circle():
    """测试圆形生成"""
    result = get_preset_svg('circle', size=180)

    assert result['status'] == 'success'
    assert result['svg_path']
    assert 'A' in result['svg_path']  # 圆弧指令
    assert result['width'] == 180
    assert result['height'] == 180
    assert result['shape'] == 'circle'
    assert result['error'] is None


def test_get_square():
    """测试正方形生成"""
    result = get_preset_svg('square', size=180)

    assert result['status'] == 'success'
    assert result['svg_path'].startswith('M')
    assert 'L' in result['svg_path']
    assert result['shape'] == 'square'


def test_get_triangle():
    """测试三角形生成"""
    result = get_preset_svg('triangle', size=180)

    assert result['status'] == 'success'
    assert result['svg_path'].count('L') == 2  # 三条边
    assert result['shape'] == 'triangle'


def test_get_star():
    """测试五角星生成"""
    result = get_preset_svg('star', size=180)

    assert result['status'] == 'success'
    assert result['svg_path'].count('L') == 9  # 10个点
    assert result['shape'] == 'star'


def test_get_heart():
    """测试心形生成"""
    result = get_preset_svg('heart', size=180)

    assert result['status'] == 'success'
    assert 'C' in result['svg_path']  # 贝塞尔曲线
    assert result['shape'] == 'heart'


def test_get_crescent():
    """测试月牙生成"""
    result = get_preset_svg('crescent', size=180)

    assert result['status'] == 'success'
    assert result['svg_path'].count('A') == 2  # 两个圆弧
    assert result['shape'] == 'crescent'


def test_unknown_shape():
    """测试未知图形"""
    result = get_preset_svg('unknown', size=180)

    assert result['status'] == 'failed'
    assert result['svg_path'] == ''
    assert 'Unknown shape' in result['error']


def test_custom_size():
    """测试自定义尺寸"""
    result = get_preset_svg('circle', size=100)

    assert result['status'] == 'success'
    assert result['width'] == 100
    assert result['height'] == 100
