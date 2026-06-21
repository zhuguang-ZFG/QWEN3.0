"""Tests for svg_validator.py"""

from xiaozhi_drawing.svg_validator import validate_svg_path


def test_valid_simple_path():
    """测试简单有效路径"""
    path = "M 10 10 L 50 50 L 100 10 Z"
    result = validate_svg_path(path)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.complexity["point_count"] == 3
    assert result.complexity["stroke_count"] == 1


def test_empty_path():
    """测试空路径"""
    result = validate_svg_path("")

    assert result.valid is False
    assert "路径为空" in result.errors[0]


def test_invalid_command():
    """测试非法指令"""
    path = "X 10 10"  # X 不是有效指令
    result = validate_svg_path(path)

    assert result.valid is False


def test_path_exceeds_workspace():
    """测试路径超出工作区"""
    path = "M 0 0 L 250 250"  # 超出 200x200
    result = validate_svg_path(path, workspace=(200, 200))

    assert result.valid is False
    assert any("超出工作区" in e for e in result.errors)


def test_path_negative_coordinates():
    """测试路径负坐标超出工作区"""
    path = "M -10 10 L 50 50"
    result = validate_svg_path(path, workspace=(200, 200))

    assert result.valid is False
    assert any("超出工作区" in e for e in result.errors)


def test_path_near_workspace_limit():
    """测试路径接近工作区边界（警告）"""
    path = "M 0 0 L 195 195"  # 接近 200x200
    result = validate_svg_path(path, workspace=(200, 200))

    assert result.valid is True
    assert any("接近工作区边界" in w for w in result.warnings)


def test_complex_path_with_curves():
    """测试包含曲线的复杂路径"""
    path = "M 10 10 C 20 20, 30 30, 40 40 Q 50 50, 60 60 Z"
    result = validate_svg_path(path)

    assert result.valid is True
    assert result.complexity["point_count"] == 3  # M + C 终点 + Q 终点


def test_max_points_exceeded():
    """测试点数超限"""
    # 生成超过限制的路径
    points = " ".join(f"L {i} {i}" for i in range(100))
    path = f"M 0 0 {points}"
    result = validate_svg_path(path, max_points=50)

    assert result.valid is False
    assert any("超过限制" in e for e in result.errors)


def test_max_points_warning():
    """测试点数接近限制（警告）"""
    points = " ".join(f"L {i} {i}" for i in range(85))
    path = f"M 0 0 {points}"
    result = validate_svg_path(path, max_points=100)

    assert result.valid is True
    assert any("接近限制" in w for w in result.warnings)


def test_multiple_strokes():
    """测试多笔画路径"""
    path = "M 10 10 L 20 20 M 30 30 L 40 40 M 50 50 L 60 60"
    result = validate_svg_path(path)

    assert result.valid is True
    assert result.complexity["stroke_count"] == 3


def test_bbox_calculation():
    """测试边界框计算"""
    path = "M 10 20 L 100 80 L 50 120"
    result = validate_svg_path(path)

    bbox = result.complexity["bbox"]
    assert bbox["min_x"] == 10
    assert bbox["max_x"] == 100
    assert bbox["min_y"] == 20
    assert bbox["max_y"] == 120
    assert bbox["width"] == 90
    assert bbox["height"] == 100
