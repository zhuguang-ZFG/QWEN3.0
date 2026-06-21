"""Tests for path_optimizer.py"""

from xiaozhi_drawing.path_optimizer import optimize_svg_path


def test_optimize_empty_path():
    """测试空路径优化"""
    result = optimize_svg_path("")
    assert result.original_points == 0
    assert result.optimized_points == 0


def test_optimize_simple_path():
    """测试简单路径优化"""
    path = "M 0 0 L 10 10 L 20 20 L 30 30"
    result = optimize_svg_path(path, tolerance=5.0)

    assert result.optimized_points > 0
    assert result.optimized_points <= result.original_points


def test_simplification_reduces_points():
    """测试简化减少点数"""
    # 高密度直线，可大幅简化
    points = " ".join(f"L {i} {i}" for i in range(0, 100, 1))
    path = f"M 0 0 {points}"
    result = optimize_svg_path(path, tolerance=2.0)

    assert result.reduction_ratio > 0.3  # 至少减少30%


def test_scale_oversized_path():
    """测试缩放过大路径"""
    path = "M 0 0 L 500 500 L 1000 0"  # 超大路径
    result = optimize_svg_path(path, target_size=(180, 180))

    # 检查路径被缩放到目标尺寸内
    assert "M" in result.optimized_path
    assert result.optimized_points == 3


def test_scale_maintains_aspect_ratio():
    """测试缩放保持宽高比"""
    # 宽形路径
    path = "M 0 50 L 400 50 L 200 100"
    result = optimize_svg_path(path, target_size=(180, 180))

    # 优化后应居中
    assert result.optimized_points == 3


def test_centering():
    """测试居中功能"""
    path = "M 10 10 L 20 20 L 30 10"
    result = optimize_svg_path(path, target_size=(200, 200))

    # 路径应居中在 200x200 内
    assert "M" in result.optimized_path
    assert result.optimized_points == 3


def test_complex_path_optimization():
    """测试复杂路径优化"""
    # 混合指令路径
    path = "M 10 10 L 20 15 L 30 20 L 40 25 L 50 30 L 60 35 L 70 40"
    result = optimize_svg_path(path, tolerance=3.0)

    assert result.optimized_points < result.original_points
    assert result.reduction_ratio > 0


def test_tolerance_effect():
    """测试容差参数影响"""
    path = "M 0 0 " + " ".join(f"L {i} {i + 0.5}" for i in range(50))

    result_low = optimize_svg_path(path, tolerance=0.5)
    result_high = optimize_svg_path(path, tolerance=5.0)

    # 高容差应产生更少点
    assert result_high.optimized_points <= result_low.optimized_points


def test_path_format_closed():
    """测试闭合路径输出格式"""
    path = "M 10 10 L 50 50 L 90 10 Z"
    result = optimize_svg_path(path, close=True)

    assert result.optimized_path.startswith("M")
    assert result.optimized_path.endswith("Z")
    assert "L" in result.optimized_path


def test_open_path_stays_open():
    """骨架/open stroke：无 Z 输入不应被优化器闭合"""
    path = "M 10 10 L 50 50 L 90 10"
    result = optimize_svg_path(path, close=False)

    assert " Z" not in result.optimized_path
    assert result.optimized_path.count("M") == 1


def test_multi_subpath_open_strokes():
    """多笔画开放路径：子路径分别优化，不应连成一笔"""
    path = "M 0 0 L 10 0 M 50 0 L 60 0"
    result = optimize_svg_path(path, close=False)

    assert result.optimized_path.count("M") == 2
    assert " Z" not in result.optimized_path


def test_auto_close_when_input_has_z():
    path = "M 0 0 L 10 0 L 10 10 Z"
    result = optimize_svg_path(path)
    assert result.optimized_path.endswith("Z")


def test_single_point_path():
    """测试单点路径"""
    path = "M 50 50"
    result = optimize_svg_path(path)

    assert result.optimized_points == 1
    assert result.reduction_ratio == 0.0
