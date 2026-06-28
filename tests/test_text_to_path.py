"""手写体字体转路径测试（text_to_path + handwriting_path 意图检测）。

真实字体效果需部署时配 LxgwWenKai.ttf 冒烟；本测试覆盖：
- text_to_svg_path 的成功/失败/缺失分支（成功用 fonttools 生成最小临时字体）
- try_text_to_handwriting 的意图检测（前缀/writing_machine/画图关键词）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from device_gateway.handwriting_path import (
    _extract_text_from_prompt,
    _is_draw_intent,
    try_text_to_handwriting,
)
from xiaozhi_drawing import text_to_path


def _build_minimal_font(tmp_path: Path) -> Path:
    """用 fonttools FontBuilder 构造一个最小可用 TTF（含 A 字形占位矩形）。

    setupGlyf 要求值是 Glyph 对象（用 TTGlyphPen 绘制），不是 dict。
    """
    from fontTools.fontBuilder import FontBuilder  # type: ignore[import-not-found]
    from fontTools.pens.ttGlyphPen import TTGlyphPen  # type: ignore[import-not-found]

    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "space", "A"])
    fb.setupCharacterMap({32: "space", 65: "A"})

    # 用 TTGlyphPen 绘制 A 的占位矩形
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((900, 0))
    pen.lineTo((900, 800))
    pen.lineTo((100, 800))
    pen.closePath()
    glyph_a = pen.glyph()

    # 空字形用 TTGlyphPen（无任何绘制）
    pen_empty = TTGlyphPen(None)
    pen_empty.moveTo((0, 0))
    pen_empty.lineTo((0, 0))
    pen_empty.closePath()
    empty = pen_empty.glyph()

    fb.setupGlyf({".notdef": empty, "space": empty, "A": glyph_a})
    fb.setupHorizontalMetrics({"space": (250, 0), "A": (1000, 100), ".notdef": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "TestHand", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.setupHead(unitsPerEm=1000)
    out = tmp_path / "test_hand.ttf"
    fb.font.save(str(out))
    return out


# ─── text_to_svg_path 分支测试 ───


def test_text_to_svg_path_empty_text():
    result = text_to_path.text_to_svg_path("")
    assert result["status"] == "failed"
    assert "empty" in result["error"]


def test_text_to_svg_path_font_missing(tmp_path):
    result = text_to_path.text_to_svg_path("hi", font_path=tmp_path / "nonexistent.ttf")
    assert result["status"] == "failed"
    assert "font missing" in result["error"]


def test_text_to_svg_path_success_with_minimal_font(tmp_path):
    font = _build_minimal_font(tmp_path)
    result = text_to_path.text_to_svg_path("A", font_path=font)
    assert result["status"] == "success", f"expected success, got: {result}"
    assert result["svg_path"]  # 非空 path
    assert result["width"] == 200  # workspace
    assert result["height"] == 200
    assert result["contour_count"] >= 1
    assert result["font"] == "test_hand.ttf"


def test_text_to_svg_path_no_renderable_chars(tmp_path):
    """字体不含目标字形（如中文）→ failed + 明确错误（非静默）。"""
    font = _build_minimal_font(tmp_path)  # 只有 A
    result = text_to_path.text_to_svg_path("你好", font_path=font)
    assert result["status"] == "failed"
    assert "renderable" in result["error"] or "no renderable" in result["error"]


# ─── handwriting_path 意图检测测试 ───


def test_extract_text_from_prompt_chinese_prefix():
    assert _extract_text_from_prompt("写：床前明月光") == "床前明月光"
    assert _extract_text_from_prompt("  写: hello world  ") == "hello world"


def test_extract_text_from_prompt_english_prefix():
    assert _extract_text_from_prompt("write: test") == "test"
    assert _extract_text_from_prompt("Write：中文") == "中文"


def test_extract_text_from_prompt_no_prefix():
    assert _extract_text_from_prompt("画一只猫") is None
    assert _extract_text_from_prompt("随便一句话") is None


def test_is_draw_intent():
    assert _is_draw_intent("画一只猫") is True
    assert _is_draw_intent("请 draw 一个圆") is True
    assert _is_draw_intent("写一首诗") is False
    assert _is_draw_intent("hello world") is False


def test_try_text_to_handwriting_no_font_returns_none(tmp_path, monkeypatch):
    """字体缺失时返回 None（让链路回退到生图，不阻断）。"""
    monkeypatch.setenv("LIMA_HANDWRITING_FONT", str(tmp_path / "missing.ttf"))
    result = try_text_to_handwriting("写：你好", device_id=None)
    assert result is None


def test_try_text_to_handwriting_draw_keyword_skips():
    """含画图关键词 → 不触发（即使有写意图也不强制）。"""
    result = try_text_to_handwriting("画一个字", device_id=None)
    assert result is None


def test_try_text_to_handwriting_success_with_font(tmp_path, monkeypatch):
    """前缀触发 + 字体可用 → 成功返回手写体路径结构。"""
    font = _build_minimal_font(tmp_path)
    monkeypatch.setenv("LIMA_HANDWRITING_FONT", str(font))
    result = try_text_to_handwriting("write: A", device_id=None)
    assert result is not None
    assert result["status"] == "success"
    assert result["svg_path"]
    assert result["model"] == "handwriting:font"
    assert result["width"] == 200


def test_try_text_to_handwriting_writing_machine_device(tmp_path, monkeypatch):
    """设备类型 writing_machine + 无画图关键词 → 整个 prompt 走字体路径。"""
    font = _build_minimal_font(tmp_path)
    monkeypatch.setenv("LIMA_HANDWRITING_FONT", str(font))
    # 直接传 device_type，绕过 resolve_device_type（避免依赖 device_profile 配置）
    result = try_text_to_handwriting("A", device_id=None, device_type="esp32_writing_machine")
    assert result is not None
    assert result["status"] == "success"


def test_try_text_to_handwriting_xy_plotter_no_prefix_returns_none():
    """xy_plotter 设备 + 无前缀 + 无画图关键词 → 不触发（走生图）。"""
    result = try_text_to_handwriting("一只猫", device_id=None, device_type="esp32_xy_plotter")
    assert result is None
