"""文字转 SVG 手写体路径（无损，fonttools 字形提取）。

与生图→骨架化互补：直接从字体字形提取矢量轮廓，跳过生图，精度无损。
字体文件不进 git，放在 xiaozhi_drawing/fonts/ 或通过环境变量指定。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from xiaozhi_drawing.font_registry import list_handwriting_fonts, resolve_font_path

logger = logging.getLogger(__name__)

_WORKSPACE = 200
_TARGET = 180
_FONT_PX = 40


def _glyph_advance(font: Any, glyph_name: str) -> float:
    """取字形水平推进宽度（font units），缺失返回 em 的 0.6。"""
    try:
        return float(font["hmtx"][glyph_name][0])
    except Exception:  # noqa: BLE001
        return float(font["head"].unitsPerEm or 1000) * 0.6


def _draw_glyph_to_path(font: Any, glyph_name: str, transform: tuple[float, float, float, float, float, float]) -> str:
    """用 TransformPen 包装 SVGPathPen，把字形按变换矩阵画成 SVG path d。"""
    from fontTools.pens.recordingPen import RecordingPen  # type: ignore[import-not-found]
    from fontTools.pens.svgPathPen import SVGPathPen  # type: ignore[import-not-found]
    from fontTools.pens.transformPen import TransformPen  # type: ignore[import-not-found]

    glyph_set = font.getGlyphSet()
    recording = RecordingPen()
    transformed = TransformPen(recording, transform)
    glyph_set[glyph_name].draw(transformed)
    out_pen = SVGPathPen({})
    recording.replay(out_pen)
    return out_pen.getCommands()


def _layout_lines(
    text: str, font: Any, cmap: dict[int, str], *, font_px: float = _FONT_PX, max_width: float = _TARGET
) -> list[list[tuple[str, str, float]]]:
    """按行布局文字，返回 lines[行] = [(char, glyph_name, advance_px)]。贪心换行。"""
    units_per_em = font["head"].unitsPerEm or 1000
    scale = font_px / units_per_em
    lines: list[list[tuple[str, str, float]]] = []
    current: list[tuple[str, str, float]] = []
    width = 0.0
    for ch in text:
        if ch in "\r\n":
            if current:
                lines.append(current)
            current, width = [], 0.0
            continue
        if ch.isspace():
            width += font_px * 0.3
            continue
        glyph_name = cmap.get(ord(ch))
        if not glyph_name:
            logger.warning("字形未覆盖，跳过字符: %r", ch)
            continue
        advance = _glyph_advance(font, glyph_name) * scale
        if width + advance > max_width and current:
            lines.append(current)
            current, width = [], 0.0
        current.append((ch, glyph_name, advance))
        width += advance
    if current:
        lines.append(current)
    return lines


def _render_lines(
    font: Any, lines: list[list[tuple[str, str, float]]], *, font_px: float = _FONT_PX, line_height_ratio: float = 1.4
) -> tuple[list[str], float, float]:
    """把每行每字按布局偏移画成 path。返回 (paths, content_w, content_h)。"""
    units_per_em = font["head"].unitsPerEm or 1000
    scale = font_px / units_per_em
    line_height = font_px * line_height_ratio
    paths: list[str] = []
    max_line_width = 0.0
    y_baseline = line_height
    for line in lines:
        line_width = sum(adv for _, _, adv in line)
        max_line_width = max(max_line_width, line_width)
        x = 0.0
        for _ch, glyph_name, adv in line:
            try:
                d = _draw_glyph_to_path(font, glyph_name, (scale, 0, 0, -scale, x, y_baseline))
                if d:
                    paths.append(d)
            except Exception as exc:  # noqa: BLE001
                logger.warning("字形渲染失败，跳过: %s", exc)
            x += adv
        y_baseline += line_height
    content_h = y_baseline - line_height
    return paths, max_line_width, content_h


def _fit_to_workspace(paths: list[str], content_w: float, content_h: float) -> list[str]:
    """整体居中缩放到 workspace (200x200)，留 10px 边距。"""
    margin = 10
    avail = _WORKSPACE - 2 * margin
    if content_w <= 0 or content_h <= 0:
        return paths
    fit_scale = min(avail / content_w, avail / content_h, 1.0)
    dx = (_WORKSPACE - content_w * fit_scale) / 2
    dy = (_WORKSPACE - content_h * fit_scale) / 2
    return [_rescale_path(p, fit_scale, dx, dy) for p in paths]


def _rescale_path(path_d: str, scale: float, dx: float, dy: float) -> str:
    """对已布局 path 做整体缩放+平移（数值成对线性变换）。"""
    if not path_d:
        return ""
    tokens = re.findall(r"[MLCQZTSmlcqztsHhVv]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", path_d)
    counts = {"M": 2, "L": 2, "C": 6, "Q": 4, "T": 2, "S": 4, "m": 2, "l": 2, "c": 6, "q": 4, "t": 2, "s": 4}
    out: list[str] = []
    i, cmd = 0, ""
    while i < len(tokens):
        t = tokens[i]
        if not t[0].isdigit() and t not in ".-":
            cmd = t
            out.append(t)
            i += 1
            continue
        count = counts.get(cmd, 0)
        if count == 0 or i + count > len(tokens):
            break
        ok = True
        for j in range(0, count, 2):
            try:
                px = float(tokens[i + j]) * scale + dx
                py = float(tokens[i + j + 1]) * scale + dy
            except (ValueError, IndexError):
                ok = False
                break
            out.extend([f"{px:.2f}", f"{py:.2f}"])
        if not ok:
            break
        i += count
    return " ".join(out) if out else ""


class FontLoadError(Exception):
    """字体加载失败（未安装、损坏或缺少 cmap）。"""


def _load_font(path: Path) -> tuple[Any, dict[int, str]]:
    """加载字体并返回 (font, cmap)；失败抛出 FontLoadError。"""
    try:
        from fontTools.ttLib import TTFont  # type: ignore[import-not-found]
    except ImportError as exc:
        logger.error("fontTools 未安装: %s", exc)
        raise FontLoadError("fonttools not installed") from exc
    try:
        font = TTFont(str(path))
    except Exception as exc:  # noqa: BLE001
        logger.error("字体文件损坏: %s", exc)
        raise FontLoadError(f"invalid font file: {exc}") from exc
    cmap = font.getBestCmap()
    if not cmap:
        raise FontLoadError("font has no cmap table")
    return font, cmap


def text_to_svg_path(
    text: str,
    *,
    font_path: Path | str | None = None,
    font_name: str | None = None,
    font_type: str = "ttf",
) -> dict[str, Any]:
    """文字 → 手写体字形 → SVG path（无损）。

    Args:
        font_type: "ttf" 使用 fonttools 从 TTF 提取字形轮廓（默认）；
                   "hershey" 使用 Hershey 单笔画字体（适合绘图机，无双线）。

    字体缺失/文字空/字形未覆盖时返回 failed + 明确错误（不静默）。
    """
    text = (text or "").strip()
    if not text:
        return _payload("failed", error="empty text")
    if font_type == "hershey":
        from xiaozhi_drawing.hershey_font import hershey_text_to_svg_path

        return hershey_text_to_svg_path(text)
    path = resolve_font_path(font_name=font_name, font_path=font_path)
    if not path.exists():
        logger.warning("手写体字体缺失: %s", path)
        return _payload("failed", error=f"handwriting font missing: {path.name}")
    try:
        font, cmap = _load_font(path)
    except FontLoadError as exc:
        return _payload("failed", error=str(exc))
    lines = _layout_lines(text, font, cmap)
    if not lines:
        return _payload("failed", error="no renderable characters (font may not cover the script)")
    paths, content_w, content_h = _render_lines(font, lines)
    if not paths:
        return _payload("failed", error="all glyphs failed to render")
    fitted = _fit_to_workspace(paths, content_w, content_h)
    return _payload(
        "success",
        svg_path=" ".join(fitted),
        width=_WORKSPACE,
        height=_WORKSPACE,
        contour_count=len(fitted),
        font=path.name,
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
    """构造与 svg_converter._svg_payload 对齐的返回结构。"""
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
