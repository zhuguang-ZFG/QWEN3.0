"""Motion coordinate pre-check for device draw SVG output (Tabbit L3)."""

from __future__ import annotations

from device_gateway.path_pipeline import render_svg_task
from device_gateway.safety import DEFAULT_WORKSPACE_MM


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
