"""Tests for device_gateway.draw_prompt_enhancer."""

from __future__ import annotations

import pytest

from device_gateway.draw_prompt_enhancer import enhance_drawing_prompt


class TestEnhanceDrawingPrompt:
    def test_includes_pen_plotter_constraints(self):
        result = enhance_drawing_prompt("猫")
        assert "笔绘机" in result
        assert "黑色线条" in result
        assert "纯白背景" in result
        assert "封闭图形" in result

    def test_includes_user_subject(self):
        result = enhance_drawing_prompt("一只在睡觉的猫")
        assert "一只在睡觉的猫" in result

    def test_default_style_and_complexity(self):
        result = enhance_drawing_prompt("星星")
        assert "简约风格" in result
        assert "中复杂度" in result
        assert "约20笔画" in result

    def test_custom_style_and_complexity(self):
        result = enhance_drawing_prompt("花", style="可爱", complexity="低")
        assert "可爱风格" in result
        assert "低复杂度" in result
        assert "约10笔画" in result

    def test_empty_prompt_falls_back(self):
        result = enhance_drawing_prompt("  ")
        assert "一个简单图形" in result

    def test_non_string_input_converted(self):
        result = enhance_drawing_prompt(123)  # type: ignore[arg-type]
        assert "123" in result

    def test_rejects_gray_and_fill(self):
        result = enhance_drawing_prompt("房子")
        assert "无阴影" in result
        assert "无填充" in result
        assert "无文字" in result


class TestEnhanceDrawingPromptSingleLineKeywords:
    def test_includes_single_stroke_style(self):
        result = enhance_drawing_prompt("猫")
        assert "单笔连续" in result
        assert "coloring book outline" in result

    def test_includes_no_gradient(self):
        result = enhance_drawing_prompt("树")
        assert "无渐变" in result

    def test_includes_one_stroke_hint(self):
        result = enhance_drawing_prompt("鸟")
        assert "一笔画成" in result

    def test_no_fixed_line_width_hint(self):
        result = enhance_drawing_prompt("花")
        assert "2-3px" not in result
        assert "粗细约" not in result


@pytest.mark.parametrize(
    "complexity,expected_strokes",
    [
        ("低", "约10笔画"),
        ("中", "约20笔画"),
        ("高", "约40笔画"),
        ("unknown", "约20笔画"),
    ],
)
def test_complexity_strokes(complexity: str, expected_strokes: str) -> None:
    result = enhance_drawing_prompt("树", complexity=complexity)
    assert expected_strokes in result
