"""Convert ASCII text to polyline motion paths using a built-in stroke font."""

from __future__ import annotations

from device_gateway.path_data import (
    FONT_BASELINE,
    FONT_CHAR_H,
    FONT_CHAR_W,
    _FONT_GLYPHS,
    clamp_path,
)


def text_to_path(
    text: str,
    origin_x: float = 5.0,
    origin_y: float = 20.0,
    scale: float = 2.0,
) -> list[dict[str, float]]:
    """Convert ASCII text to a polyline motion path using the built-in stroke font.

    Returns a list of {"x": ..., "y": ..., "z": 0} points suitable for
    run_path dispatch. Pen-up transitions between glyphs and segments
    are encoded as consecutive identical points (the U8 controller
    interprets these as rapid moves).
    """
    path: list[dict[str, float]] = []
    pen_down = False
    cursor_x = origin_x

    for ch in text:
        glyph = _FONT_GLYPHS.get(ch, _FONT_GLYPHS.get("?"))
        if not glyph:
            cursor_x += FONT_CHAR_W * scale
            continue

        for item in glyph:
            if len(item) == 3 and item[0] is None:
                # Pen-up: move to position without drawing
                if pen_down and path:
                    pen_down = False
                px = cursor_x + float(item[1]) * scale
                py = origin_y - float(item[2]) * scale
                path.append({"x": round(px, 2), "y": round(py, 2), "z": 0})
            else:
                # Pen-down: draw line to position
                px = cursor_x + float(item[0]) * scale
                py = origin_y - float(item[1]) * scale
                path.append({"x": round(px, 2), "y": round(py, 2), "z": 0})
                pen_down = True

        cursor_x += FONT_CHAR_W * scale

    return clamp_path(path)
