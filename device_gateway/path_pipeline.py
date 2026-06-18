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

from typing import Any

from device_gateway.path_data import MAX_PATH_POINTS
from device_gateway.preview_svg import preview_svg
from device_gateway.svg_parser import svg_path_to_motion
from device_gateway.text_renderer import text_to_path


def render_text_task(text: str) -> dict[str, Any]:
    """Render a write_text intent into a motion task params dict with preview."""
    path = text_to_path(text[:40])
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
        {"x": round(origin_x + pt["x"] * scale, 2), "y": round(origin_y + pt["y"] * scale, 2), "z": 0}
        for pt in path
    ]


def render_svg_task(d_string: str) -> dict[str, Any]:
    """Render an SVG path string into a motion task params dict with preview."""
    path = svg_path_to_motion(d_string[:2000])
    path = _normalize_path_to_workspace(path)
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f"svg path — {len(path)} pts"),
        "point_count": len(path),
    }
