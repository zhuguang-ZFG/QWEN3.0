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


def render_svg_task(d_string: str) -> dict[str, Any]:
    """Render an SVG path string into a motion task params dict with preview."""
    path = svg_path_to_motion(d_string[:2000])
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f"svg path — {len(path)} pts"),
        "point_count": len(path),
    }
