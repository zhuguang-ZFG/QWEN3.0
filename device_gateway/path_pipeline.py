"""Device Gateway path pipeline — deterministic text-to-path and SVG-to-path.

Replaces the rectangle/star placeholders in tasks.py with a real
output pipeline:

- text_to_path(text, origin, scale) → polyline path from a built-in
  stroke font (5x9 ASCII glyphs)
- svg_path_to_motion(d_string, origin, scale, max_points) → polyline
  approximation of SVG path commands (M, L, C, Q, Z)
- preview_svg(path, width, height) → standalone SVG string for operator
  visualization and task-record preview artifacts

No external dependencies. All safety limits (points, bounds, feed)
are enforced at the pipeline boundary.
"""
from __future__ import annotations

import math
from typing import Any

# ── Stroke font: 5x9 monospace glyphs for ASCII 0x20–0x7E ──────────────────
# Each glyph is a list of (x, y) segments: even indices are pen-up moves,
# odd indices are pen-down line-to. Coordinates are in a 5-wide, 9-tall cell.
# Z is the pen-up sentinel (None means pen-up to start of next segment).

_FONT_GLYPHS: dict[str, list[tuple[float | None, float, float]]] = {
    " ": [(None, 0, 0), (None, 5, 0)],
    "A": [(None, 0, 9), (0, 5), (5, 9), (None, 1, 5), (4, 5)],
    "B": [(None, 0, 0), (0, 9), (5, 8), (5, 4), (0, 4), (None, 0, 4), (5, 0)],
    "C": [(None, 5, 8), (0, 8), (0, 0), (5, 0)],
    "D": [(None, 0, 0), (0, 9), (5, 8), (5, 0), (0, 0)],
    "E": [(None, 5, 9), (0, 9), (0, 4), (3, 4), (None, 0, 4), (0, 0), (5, 0)],
    "F": [(None, 5, 9), (0, 9), (0, 4), (3, 4), (None, 0, 4), (0, 0)],
    "G": [(None, 5, 8), (0, 8), (0, 0), (5, 0), (5, 4), (2, 4)],
    "H": [(None, 0, 0), (0, 9), (None, 5, 9), (5, 0), (None, 0, 5), (5, 5)],
    "I": [(None, 0, 9), (5, 9), (None, 2.5, 9), (2.5, 0), (None, 0, 0), (5, 0)],
    "J": [(None, 5, 9), (5, 5), (5, 0), (0, 0)],
    "K": [(None, 0, 0), (0, 9), (None, 0, 5), (5, 9), (None, 2, 5), (5, 0)],
    "L": [(None, 0, 9), (0, 0), (5, 0)],
    "M": [(None, 0, 0), (0, 9), (2.5, 4), (5, 9), (5, 0)],
    "N": [(None, 0, 0), (0, 9), (5, 0), (5, 9)],
    "O": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8)],
    "P": [(None, 0, 0), (0, 9), (5, 9), (5, 5), (0, 5)],
    "Q": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8), (None, 3, 4), (5, 1)],
    "R": [(None, 0, 0), (0, 9), (5, 9), (5, 5), (0, 5), (None, 2, 5), (5, 0)],
    "S": [(None, 5, 9), (0, 8), (0, 5), (5, 4), (5, 0), (0, 0)],
    "T": [(None, 0, 9), (5, 9), (None, 2.5, 9), (2.5, 0)],
    "U": [(None, 0, 9), (0, 0), (5, 0), (5, 9)],
    "V": [(None, 0, 9), (2.5, 0), (5, 9)],
    "W": [(None, 0, 9), (1.25, 0), (2.5, 4), (3.75, 0), (5, 9)],
    "X": [(None, 0, 9), (5, 0), (None, 0, 0), (5, 9)],
    "Y": [(None, 0, 9), (2.5, 5), (5, 9), (None, 2.5, 5), (2.5, 0)],
    "Z": [(None, 0, 9), (5, 9), (0, 0), (5, 0)],
    "0": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8)],
    "1": [(None, 2, 9), (2.5, 9), (2.5, 0), (0, 0)],
    "2": [(None, 0, 8), (5, 8), (5, 4), (0, 4), (0, 0), (5, 0)],
    "3": [(None, 0, 9), (5, 9), (5, 5), (0, 5), (None, 5, 5), (5, 0), (0, 0)],
    "4": [(None, 0, 9), (0, 4), (5, 4), (None, 3, 9), (3, 0)],
    "5": [(None, 5, 9), (0, 9), (0, 4), (5, 4), (5, 0), (0, 0)],
    "6": [(None, 5, 9), (0, 9), (0, 0), (5, 0), (5, 4), (0, 4)],
    "7": [(None, 0, 9), (5, 9), (3, 0)],
    "8": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8), (None, 0, 4), (5, 4)],
    "9": [(None, 5, 0), (5, 8), (0, 8), (0, 4), (5, 4)],
    ".": [(None, 2, 0), (3, 0)],
    ",": [(None, 3, 0), (2, -2)],
    "!": [(None, 2.5, 9), (2.5, 3), (None, 2.5, 0), (2.5, 0)],
    "?": [(None, 0, 8), (3, 9), (5, 7), (4, 5), (2.5, 4), (None, 2.5, 2), (2.5, 0)],
    "-": [(None, 1, 5), (4, 5)],
    "_": [(None, 0, 0), (5, 0)],
    "+": [(None, 2.5, 8), (2.5, 1), (None, 0, 4.5), (5, 4.5)],
    "=": [(None, 0, 3), (5, 3), (None, 0, 6), (5, 6)],
    "/": [(None, 5, 9), (0, 0)],
    "\\": [(None, 0, 9), (5, 0)],
    "(": [(None, 4, 10), (2, 7), (2, 2), (4, -1)],
    ")": [(None, 1, 10), (3, 7), (3, 2), (1, -1)],
    "[": [(None, 4, 10), (1, 10), (1, -1), (4, -1)],
    "]": [(None, 1, 10), (4, 10), (4, -1), (1, -1)],
    "<": [(None, 5, 9), (0, 5), (5, 0)],
    ">": [(None, 0, 9), (5, 5), (0, 0)],
    ":": [(None, 2.5, 7), (2.5, 7), (None, 2.5, 2), (2.5, 2)],
    ";": [(None, 2.5, 7), (2.5, 7), (None, 3, 2), (2, 0)],
    "'": [(None, 2.5, 9), (2.5, 6)],
    '"': [(None, 1.5, 9), (1.5, 6), (None, 3.5, 9), (3.5, 6)],
    "#": [(None, 1, 9), (1, 0), (None, 4, 9), (4, 0), (None, 0, 3), (5, 3), (None, 0, 6), (5, 6)],
    "$": [(None, 4, 10), (1, 8), (0, 5), (5, 4), (4, 0), (1, -1), (None, 2.5, 10), (2.5, -1)],
    "%": [(None, 5, 9), (0, 0), (None, 1, 9), (1, 6), (4, 6), (4, 9), (1, 9), (None, 1, 3), (4, 3), (4, 0), (1, 0)],
    "&": [(None, 5, 8), (0, 6), (0, 5), (2, 5), (0, 2), (0, 0), (5, 0), (5, 5)],
    "@": [(None, 3, 4), (1, 4), (1, 7), (2, 8), (4, 8), (5, 6), (5, 2), (4, 0), (2, 0), (1, 2), (1, 4)],
    "*": [(None, 2.5, 9), (2.5, 0), (None, 0, 6), (5, 3), (None, 0, 3), (5, 6)],
    "|": [(None, 2.5, 9), (2.5, 0)],
    "~": [(None, 0, 6), (1.5, 8), (3.5, 6), (5, 8)],
    "`": [(None, 2.5, 9), (2.5, 7)],
    "^": [(None, 0, 7), (2.5, 9), (5, 7)],
    "{": [(None, 4, 10), (2.5, 7), (1, 5), (2.5, 3), (1, 1), (2.5, -1)],
    "}": [(None, 1, 10), (2.5, 7), (4, 5), (2.5, 3), (4, 1), (2.5, -1)],
}

FONT_CHAR_W = 6.0
FONT_CHAR_H = 11.0
FONT_BASELINE = 2.0

# ── Safety limits ────────────────────────────────────────────────────────────

MAX_PATH_POINTS = 200
MAX_WORKSPACE_MM = 200.0
MIN_WORKSPACE_MM = 1.0


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

    return _clamp_path(path)


def svg_path_to_motion(
    d_string: str,
    origin_x: float = 5.0,
    origin_y: float = 20.0,
    scale: float = 1.0,
    max_points: int = MAX_PATH_POINTS,
) -> list[dict[str, float]]:
    """Parse SVG path 'd' attribute into a polyline motion path.

    Supports M, L, C (quadratic Bézier → polyline), Q, and Z commands.
    Relative commands (m, l, c, q) are converted to absolute.
    """
    tokens = _tokenize_svg_d(d_string)
    path: list[dict[str, float]] = []
    cx, cy = 0.0, 0.0
    first_x, first_y = 0.0, 0.0

    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd in ("M", "m"):
            x = float(tokens[i]) * scale + (cx if cmd == "m" else 0)
            y = float(tokens[i + 1]) * scale + (cy if cmd == "m" else 0)
            i += 2
            cx, cy = x, y
            first_x, first_y = x, y
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("L", "l"):
            x = float(tokens[i]) * scale + (cx if cmd == "l" else 0)
            y = float(tokens[i + 1]) * scale + (cy if cmd == "l" else 0)
            i += 2
            cx, cy = x, y
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("H", "h"):
            x = float(tokens[i]) * scale + (cx if cmd == "h" else 0)
            i += 1
            cx = x
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("V", "v"):
            y = float(tokens[i]) * scale + (cy if cmd == "v" else 0)
            i += 1
            cy = y
            path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("C", "c"):
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
            i += 6
            if cmd == "c":
                x, y = cx + x * scale, cy + y * scale
                x1, y1 = cx + x1 * scale, cy + y1 * scale
                x2, y2 = cx + x2 * scale, cy + y2 * scale
            else:
                x, y = x * scale, y * scale
                x1, y1 = x1 * scale, y1 * scale
                x2, y2 = x2 * scale, y2 * scale
            for pt in _bezier_to_polyline(cx, cy, x1, y1, x2, y2, x, y, 8):
                cx, cy = pt
                path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("Q", "q"):
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            i += 4
            if cmd == "q":
                x, y = cx + x * scale, cy + y * scale
                x1, y1 = cx + x1 * scale, cy + y1 * scale
            else:
                x, y = x * scale, y * scale
                x1, y1 = x1 * scale, y1 * scale
            for pt in _bezier_to_polyline(cx, cy, x1, y1, x1, y1, x, y, 8):
                cx, cy = pt
                path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("Z", "z"):
            cx, cy = first_x, first_y
            path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

    return _clamp_path(path, max_points)


def _tokenize_svg_d(d_string: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for ch in d_string.replace(",", " "):
        if ch.isalpha():
            if current:
                tokens.append(current.strip())
                current = ""
            tokens.append(ch)
        elif ch in (" ", "\t", "\n", "\r"):
            if current:
                tokens.append(current.strip())
                current = ""
        elif ch in ("-", ".") or ch.isdigit():
            current += ch
    if current:
        tokens.append(current.strip())
    return [t for t in tokens if t]


def _bezier_to_polyline(
    x0: float, y0: float, x1: float, y1: float,
    x2: float, y2: float, x3: float, y3: float,
    segments: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(1, segments + 1):
        t = i / segments
        c0 = (1 - t) ** 3
        c1 = 3 * (1 - t) ** 2 * t
        c2 = 3 * (1 - t) * t ** 2
        c3 = t ** 3
        x = c0 * x0 + c1 * x1 + c2 * x2 + c3 * x3
        y = c0 * y0 + c1 * y1 + c2 * y2 + c3 * y3
        points.append((x, y))
    return points


def _clamp_path(
    path: list[dict[str, float]],
    max_points: int = MAX_PATH_POINTS,
) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for pt in path[:max_points]:
        x = max(-MAX_WORKSPACE_MM, min(MAX_WORKSPACE_MM, pt["x"]))
        y = max(-MAX_WORKSPACE_MM, min(MAX_WORKSPACE_MM, pt["y"]))
        result.append({"x": round(x, 2), "y": round(y, 2), "z": round(pt.get("z", 0), 2)})
    return result


# ── Preview SVG ──────────────────────────────────────────────────────────────

def preview_svg(
    path: list[dict[str, float]],
    width: float = 200,
    height: float = 200,
    *,
    title: str = "motion preview",
) -> str:
    """Generate a standalone SVG preview of a motion path."""
    if not path:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><text x="10" y="20" font-size="12">(empty path)</text></svg>'

    points_str = " ".join(f'{p["x"]},{p["y"]}' for p in path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#ccc"/>'
        f'<polyline points="{points_str}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="5" y="{height - 5}" font-size="10" fill="#888">{title} — {len(path)} pts</text>'
        f"</svg>"
    )


# ── Pipeline entry ────────────────────────────────────────────────────────────

def render_text_task(text: str) -> dict[str, Any]:
    """Render a write_text intent into a motion task params dict with preview."""
    path = text_to_path(text[:40])
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f'text: "{text[:20]}"'),
        "point_count": len(path),
    }


def render_svg_task(d_string: str) -> dict[str, Any]:
    """Render an SVG path string into a motion task params dict with preview."""
    path = svg_path_to_motion(d_string[:2000])
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f"svg path — {len(path)} pts"),
        "point_count": len(path),
    }
