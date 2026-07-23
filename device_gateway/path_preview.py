"""SVG preview/d rendering for motion paths.

Pure presentation helpers extracted from path_pipeline so the path-generation
module stays well under the 300-line size gate. These read only x/y/z from
point dicts and ``html`` from the stdlib — no motion-path or workspace logic.
"""

from __future__ import annotations

import html


def motion_path_to_svg_d(path: list[dict[str, float]]) -> str:
    """Serialize a motion path to an SVG ``d`` string.

    Pen-up moves (``z > 0`` safe-height travel, or legacy consecutive
    duplicate points) emit ``M``; drawing points emit ``L``.
    """
    if not path:
        return ""
    parts: list[str] = []
    prev_pt: dict[str, float] | None = None
    pending_move = True
    for pt in path:
        is_duplicate = prev_pt is not None and pt["x"] == prev_pt["x"] and pt["y"] == prev_pt["y"]
        if float(pt.get("z", 0.0)) > 0:
            parts.append(f"M {pt['x']},{pt['y']}")
            pending_move = False
            prev_pt = pt
            continue
        if is_duplicate:
            pending_move = True
            continue
        cmd = "M" if pending_move else "L"
        parts.append(f"{cmd} {pt['x']},{pt['y']}")
        pending_move = False
        prev_pt = pt
    return " ".join(parts)


def path_bounds_with_margin(path: list[dict[str, float]], margin: float = 2.0) -> tuple[int, int]:
    """Return (width, height) covering the path bounding box plus ``margin``."""
    if not path:
        return int(margin * 2), int(margin * 2)
    xs = [pt["x"] for pt in path]
    ys = [pt["y"] for pt in path]
    return max(int(max(xs) + margin), 1), max(int(max(ys) + margin), 1)


def preview_svg(
    path: list[dict[str, float]],
    width: float = 200,
    height: float = 200,
    *,
    title: str = "motion preview",
) -> str:
    """Generate a standalone SVG preview of a motion path.

    Travel moves render via ``<path d>`` (z > 0 => ``M``) so pen-up repositioning
    is not drawn as a solid line.
    """
    if not path:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
            f'<text x="10" y="20" font-size="12">(empty path)</text></svg>'
        )

    d_string = motion_path_to_svg_d(path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#ccc"/>'
        f'<path d="{d_string}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="5" y="{height - 5}" font-size="10" fill="#888">{html.escape(title)} — {len(path)} pts</text>'
        f"</svg>"
    )
