"""Device Gateway path pipeline — deterministic text-to-path and SVG-to-path.

Replaces the rectangle/star placeholders in tasks.py with a real
output pipeline:

- text_to_path(text, origin, scale) → polyline path from a built-in
  stroke font (5x9 ASCII glyphs)
- svg_path_to_motion(d_string, origin, scale, max_points) → polyline
  approximation of SVG path commands (M, L, C, Q, Z)
- preview_svg(path, width, height) → standalone SVG string for operator
  visualization and task-record preview artifacts
- precheck_draw_motion_path(d_string) → workspace bounds pre-check

No external dependencies. All safety limits (points, bounds, feed)
are enforced at the pipeline boundary.
"""

from __future__ import annotations

from typing import Any

import html

from device_gateway.path_data import (
    FONT_CHAR_W,
    MAX_PATH_POINTS,  # noqa: F401  re-export imported by tests
    _FONT_GLYPHS,
    clamp_path,
)
from device_gateway.path_optimizer import PathOptimizer, apply_multi_pass
from device_gateway.safety import DEFAULT_WORKSPACE_MM
from device_gateway.svg_parser import svg_path_to_motion


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


def _motion_path_to_svg_d(path: list[dict[str, float]]) -> str:
    """Convert a polyline motion path into an SVG path `d` string.

    Consecutive identical points are treated as pen-up moves (rapid moves),
    so the next distinct point starts a new stroke with `M`.
    """
    if not path:
        return ""
    parts: list[str] = []
    prev_pt: dict[str, float] | None = None
    pending_move = True
    for pt in path:
        if prev_pt is not None and pt["x"] == prev_pt["x"] and pt["y"] == prev_pt["y"]:
            pending_move = True
            continue
        cmd = "M" if pending_move else "L"
        parts.append(f"{cmd} {pt['x']} {pt['y']}")
        pending_move = False
        prev_pt = pt
    return " ".join(parts)


def _path_bounds_with_margin(path: list[dict[str, float]], margin: float = 2.0) -> tuple[int, int]:
    """Return a (width, height) bounding box that contains every point."""
    if not path:
        return int(margin * 2), int(margin * 2)
    xs = [pt["x"] for pt in path]
    ys = [pt["y"] for pt in path]
    width = int(max(xs) + margin)
    height = int(max(ys) + margin)
    return max(width, 1), max(height, 1)


def text_to_svg_path(text: str) -> dict[str, Any]:
    """Render ASCII text to an SVG path suitable for plotter preview."""
    rendered = render_text_task(text[:80])
    path = rendered["path"]
    d_string = _motion_path_to_svg_d(path)
    width, height = _path_bounds_with_margin(path)
    return {
        "status": "success",
        "svg_path": d_string,
        "width": width,
        "height": height,
        "point_count": len(path),
        "path": path,
        "preview_svg": rendered["preview_svg"],
        "backend": "lima-local",
    }


def render_text_task(
    text: str,
    passes: int = 1,
    offset_mm: float = 0.5,
    optimize: bool = True,
) -> dict[str, Any]:
    """Render a write_text intent into a motion task params dict with preview."""
    path = text_to_path(text[:40])
    if passes > 1:
        path = apply_multi_pass(path, passes, offset_mm)
    if optimize:
        optimizer = PathOptimizer()
        path = optimizer.smooth(optimizer.compress(path))
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f'text: "{text[:20]}"'),
        "point_count": len(path),
    }


def _normalize_path_to_workspace(
    path: list[dict[str, float]], width: float = 100.0, height: float = 100.0, margin: float = 2.0
) -> list[dict[str, float]]:
    """Scale and translate a path so all points fit inside [0, width] x [0, height]."""
    if not path:
        return path
    xs = [pt["x"] for pt in path]
    ys = [pt["y"] for pt in path]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x
    span_y = max_y - min_y
    available_w = width - 2 * margin
    available_h = height - 2 * margin
    if span_x <= 0 or span_y <= 0:
        scale = 1.0
    else:
        scale = min(available_w / span_x, available_h / span_y, 1.0)
    origin_x = margin - min_x * scale
    origin_y = margin - min_y * scale
    return [
        {"x": round(origin_x + pt["x"] * scale, 2), "y": round(origin_y + pt["y"] * scale, 2), "z": 0} for pt in path
    ]


def render_svg_task(
    d_string: str,
    passes: int = 1,
    offset_mm: float = 0.5,
    optimize: bool = True,
) -> dict[str, Any]:
    """Render an SVG path string into a motion task params dict with preview."""
    path = svg_path_to_motion(d_string[:2000])
    path = _normalize_path_to_workspace(path)
    if passes > 1:
        path = apply_multi_pass(path, passes, offset_mm)
    if optimize:
        optimizer = PathOptimizer()
        path = optimizer.smooth(optimizer.compress(path))
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f"svg path — {len(path)} pts"),
        "point_count": len(path),
    }


def precheck_draw_motion_path(d_string: str) -> str | None:
    """Return an error message when motion coordinates exceed workspace; else None."""
    if not d_string or not d_string.strip():
        return "empty svg path"
    rendered = render_svg_task(d_string)
    path = rendered.get("path") or []
    if not path:
        return "empty motion path"
    max_x = float(DEFAULT_WORKSPACE_MM["x"])
    max_y = float(DEFAULT_WORKSPACE_MM["y"])
    max_z = float(DEFAULT_WORKSPACE_MM["z"])
    for idx, pt in enumerate(path):
        x = float(pt.get("x", 0.0))
        y = float(pt.get("y", 0.0))
        z = float(pt.get("z", 0.0))
        if not (0 <= x <= max_x and 0 <= y <= max_y and 0 <= z <= max_z):
            return f"motion point {idx} ({x},{y},{z}) outside workspace {max_x}x{max_y}mm"
    return None


def preview_svg(
    path: list[dict[str, float]],
    width: float = 200,
    height: float = 200,
    *,
    title: str = "motion preview",
) -> str:
    """Generate a standalone SVG preview of a motion path."""
    if not path:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
            f'<text x="10" y="20" font-size="12">(empty path)</text></svg>'
        )

    points_str = " ".join(f"{p['x']},{p['y']}" for p in path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#ccc"/>'
        f'<polyline points="{points_str}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="5" y="{height - 5}" font-size="10" fill="#888">{html.escape(title)} — {len(path)} pts</text>'
        f"</svg>"
    )
