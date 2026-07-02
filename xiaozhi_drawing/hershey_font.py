"""Hershey 单笔画字体渲染器。

将文本转换为 SVG 路径，使用 Hershey 字体数据。
适配 200x200 工作区，自动缩放和居中。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from xiaozhi_drawing.hershey_font_data import GLYPHS as _GLYPHS

logger = logging.getLogger(__name__)

_WORKSPACE = 200
_TARGET = 180
_FONT_PX = 40
_CAP_HEIGHT = 21
_SPACE_WIDTH = 12


def _stroke_to_svg_path(
    stroke: list[tuple[int, int]], *, scale: float, x_offset: float, y_offset: float
) -> str:
    """将一条折线转换为 SVG path data（开放路径，无 Z）。"""
    if not stroke:
        return ""
    parts: list[str] = []
    for i, (x, y) in enumerate(stroke):
        px = x_offset + x * scale
        py = y_offset - y * scale
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd} {px:.2f} {py:.2f}")
    return " ".join(parts)


def _resolve_char(ch: str) -> tuple[int, list[list[tuple[int, int]]]] | None:
    """查表返回字符的 (advance_width, strokes)。"""
    return _GLYPHS.get(ch)


def _layout_text(
    text: str, *, scale: float, max_width: float
) -> list[list[tuple[str, int]]]:
    """将文本按行排版，返回每行的 (char, x_offset) 列表。"""
    lines: list[list[tuple[str, int]]] = []
    for raw_line in text.split("\n"):
        line: list[tuple[str, int]] = []
        x = 0.0
        for ch in raw_line:
            glyph = _resolve_char(ch)
            if glyph is None:
                continue
            advance, _ = glyph
            line.append((ch, int(x)))
            x += advance * scale
        if line:
            lines.append(line)
    return lines


def _render_lines(
    lines: list[list[tuple[str, int]]], *, font_px: float
) -> tuple[list[str], float, float]:
    """渲染所有行为 SVG 路径列表，返回 (paths, content_w, content_h)。"""
    scale = font_px / _CAP_HEIGHT
    all_paths: list[str] = []
    line_height = font_px * 1.2
    max_w = 0.0

    for line_idx, line in enumerate(lines):
        y_base = (line_idx + 1) * line_height
        for ch, x_offset in line:
            glyph = _resolve_char(ch)
            if glyph is None:
                continue
            _, strokes = glyph
            for stroke in strokes:
                path = _stroke_to_svg_path(
                    stroke, scale=scale, x_offset=float(x_offset), y_offset=y_base
                )
                if path:
                    all_paths.append(path)
            advance = glyph[0]
            line_w = x_offset + advance * scale
            if line_w > max_w:
                max_w = line_w

    content_h = len(lines) * line_height if lines else 0.0
    return all_paths, max_w, content_h


def _fit_to_workspace(
    paths: list[str], content_w: float, content_h: float
) -> list[str]:
    """缩放路径以适应工作区，保持居中。"""
    if not paths:
        return paths

    if content_w > 0 and content_h > 0:
        scale = min(_TARGET / content_w, _TARGET / content_h, 1.0)
    else:
        scale = 1.0

    dx = (_WORKSPACE - content_w * scale) / 2
    dy = (_WORKSPACE - content_h * scale) / 2 + content_h * scale

    return [_rescale_path(p, scale, dx, dy) for p in paths]


def _rescale_path(path_d: str, scale: float, dx: float, dy: float) -> str:
    """对 SVG path data 应用缩放和平移。"""
    def replace_coords(match: re.Match[str]) -> str:
        cmd = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        nx = x * scale + dx
        ny = y * scale + dy
        return f"{cmd} {nx:.2f} {ny:.2f}"

    return re.sub(r"([ML])\s+([\d.]+)\s+([\d.]+)", replace_coords, path_d)


def hershey_text_to_svg_path(text: str, *, font_px: float = _FONT_PX) -> dict[str, Any]:
    """将文本渲染为 SVG 路径。"""
    if not text or not text.strip():
        return _payload("failed", error="text is empty or whitespace-only")

    has_any = False
    for ch in text:
        if ch in _GLYPHS:
            has_any = True
        elif ch in ("\n", " "):
            continue
        elif ord(ch) > 127:
            return _payload("failed", error=f"unsupported character: {ch!r}")

    if not has_any:
        return _payload("failed", error="no renderable characters")

    scale = font_px / _CAP_HEIGHT
    lines = _layout_text(text, scale=scale, max_width=_TARGET)
    if not lines:
        return _payload("failed", error="no renderable characters after layout")

    paths, content_w, content_h = _render_lines(lines, font_px=font_px)
    if not paths:
        return _payload("failed", error="no paths generated")

    paths = _fit_to_workspace(paths, content_w, content_h)
    svg_path = " ".join(paths)

    return _payload(
        "success",
        svg_path=svg_path,
        width=_WORKSPACE,
        height=_WORKSPACE,
        contour_count=len(paths),
        font="hershey-sans",
    )


def _payload(
    status: str,
    *,
    svg_path: str = "",
    width: int = 0,
    height: int = 0,
    contour_count: int = 0,
    font: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """构造返回字典。"""
    return {
        "status": status,
        "svg_path": svg_path,
        "width": width,
        "height": height,
        "contour_count": contour_count,
        "skeleton_applied": False,
        "thinning_method": None,
        "threshold_method": None,
        "font": font,
        "error": error,
    }
