"""Hershey 单笔画字体测试。"""

from __future__ import annotations

import pytest

from xiaozhi_drawing.hershey_font import (
    _stroke_to_svg_path,
    hershey_text_to_svg_path,
)
from xiaozhi_drawing.hershey_font_data import GLYPHS as _GLYPHS
from xiaozhi_drawing.text_to_path import text_to_svg_path


class TestGlyphData:
    """字体数据完整性。"""

    def test_uppercase_complete(self):
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert ch in _GLYPHS, f"缺少大写字母: {ch}"

    def test_lowercase_complete(self):
        for ch in "abcdefghijklmnopqrstuvwxyz":
            assert ch in _GLYPHS, f"缺少小写字母: {ch}"

    def test_digits_complete(self):
        for ch in "0123456789":
            assert ch in _GLYPHS, f"缺少数字: {ch}"

    def test_space_has_zero_strokes(self):
        assert _GLYPHS[" "][1] == []

    def test_all_glyphs_have_width(self):
        for ch, (width, _) in _GLYPHS.items():
            assert width > 0, f"字符 {ch!r} 宽度为 0"


class TestStrokeToSvgPath:
    """单笔画渲染。"""

    def test_single_point(self):
        stroke = [(5, 10)]
        path = _stroke_to_svg_path(stroke, scale=1.0, x_offset=0.0, y_offset=0.0)
        assert path.startswith("M 5.00")

    def test_multi_point_open_path(self):
        stroke = [(0, 0), (10, 0), (10, 10)]
        path = _stroke_to_svg_path(stroke, scale=1.0, x_offset=0.0, y_offset=0.0)
        assert "M " in path
        assert "L " in path
        assert "Z" not in path  # 开放路径，无 Z

    def test_y_flip(self):
        """Hershey Y 向上 → SVG Y 向下，应翻转。"""
        stroke = [(0, 21)]
        path = _stroke_to_svg_path(stroke, scale=1.0, x_offset=0.0, y_offset=100.0)
        # y_offset=100, y=21 → py = 100 - 21*1 = 79
        assert "79.00" in path

    def test_scale_applied(self):
        stroke = [(0, 0), (10, 10)]
        path = _stroke_to_svg_path(stroke, scale=2.0, x_offset=0.0, y_offset=0.0)
        # scale=2 → (0,0) → (20, -20)
        assert "20.00" in path

    def test_offset_applied(self):
        stroke = [(0, 0)]
        path = _stroke_to_svg_path(stroke, scale=1.0, x_offset=5.0, y_offset=10.0)
        assert "M 5.00 10.00" == path

    def test_empty_stroke(self):
        assert _stroke_to_svg_path([], scale=1.0, x_offset=0.0, y_offset=0.0) == ""


class TestHersheyTextToSvgPath:
    """端到端文字渲染。"""

    def test_simple_text(self):
        result = hershey_text_to_svg_path("Hello")
        assert result["status"] == "success"
        assert result["svg_path"]
        assert result["width"] == 200
        assert result["height"] == 200
        assert result["font"] == "hershey-sans"
        assert result["contour_count"] > 0

    def test_single_char(self):
        result = hershey_text_to_svg_path("A")
        assert result["status"] == "success"
        assert result["svg_path"].startswith("M ")

    def test_open_paths_no_z(self):
        """Hershey 路径应为开放路径，不含 Z。"""
        result = hershey_text_to_svg_path("ABC")
        assert result["status"] == "success"
        assert "Z" not in result["svg_path"]

    def test_empty_text(self):
        result = hershey_text_to_svg_path("")
        assert result["status"] == "failed"
        assert "empty" in result["error"]

    def test_whitespace_only(self):
        result = hershey_text_to_svg_path("   ")
        assert result["status"] == "failed"

    def test_unsupported_char_skipped(self):
        """不支持的字符应跳过而非崩溃。"""
        result = hershey_text_to_svg_path("A@B")
        assert result["status"] == "success"
        assert result["contour_count"] > 0

    def test_lowercase_works(self):
        result = hershey_text_to_svg_path("abc")
        assert result["status"] == "success"
        assert result["contour_count"] > 0

    def test_digits_works(self):
        result = hershey_text_to_svg_path("0123")
        assert result["status"] == "success"
        assert result["contour_count"] > 0

    def test_multiline_text(self):
        result = hershey_text_to_svg_path("Hello\nWorld")
        assert result["status"] == "success"
        assert result["contour_count"] > 5  # 多行应有更多笔画

    def test_chinese_falls_back_to_warning(self):
        """中文不在 Hershey 覆盖范围，应返回 failed。"""
        result = hershey_text_to_svg_path("你好")
        assert result["status"] == "failed"


class TestTextToPathIntegration:
    """text_to_svg_path font_type 参数集成。"""

    def test_font_type_hershey(self):
        result = text_to_svg_path("Test", font_type="hershey")
        assert result["status"] == "success"
        assert result["font"] == "hershey-sans"

    def test_font_type_ttf_default(self):
        """默认 font_type=ttf 不影响现有行为。"""
        # 不实际加载 TTF（可能未安装），只验证参数传递不报错
        result = text_to_svg_path("", font_type="ttf")
        assert result["status"] == "failed"
        assert "empty" in result["error"]
