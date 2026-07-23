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

from typing import Any  # used by workspace_mm / profile kwargs

import html
import math

from device_gateway.path_data import (
    FONT_CHAR_W,
    MAX_PATH_POINTS,  # noqa: F401  re-export imported by tests
    PEN_UP_Z,
    _FONT_GLYPHS,
    clamp_path,
)
from device_gateway.path_decimate import decimate_to_max_points
from device_gateway.path_optimizer import PathOptimizer, apply_multi_pass
from device_gateway.path_workspace import resolve_workspace_mm
from device_gateway.svg_parser import svg_path_to_motion


class PathNormalizationError(ValueError):
    """Raised when a generated path cannot fit the workspace (GW-B2)."""


def text_to_path(
    text: str,
    origin_x: float = 5.0,
    origin_y: float = 20.0,
    scale: float = 2.0,
    max_points: int = MAX_PATH_POINTS,
) -> list[dict[str, float]]:
    """ASCII stroke-font polyline; pen-up reposition points carry z > 0.

    Pen state is written per point (previously computed but never emitted):
    stroke/glyph repositioning moves (font ``None`` markers) get z = PEN_UP_Z
    (travel at safe height), drawing points get z = 0. Over-budget paths are
    decimated per-stroke (Douglas-Peucker) instead of silently truncated.
    """
    path: list[dict[str, float]] = []
    cursor_x = origin_x
    for ch in text:
        glyph = _FONT_GLYPHS.get(ch, _FONT_GLYPHS.get("?"))
        if not glyph:
            cursor_x += FONT_CHAR_W * scale
            continue
        for item in glyph:
            if len(item) == 3 and item[0] is None:
                # Pen-up reposition (stroke start / inter-glyph travel).
                px = cursor_x + float(item[1]) * scale
                py = origin_y - float(item[2]) * scale
                path.append({"x": round(px, 2), "y": round(py, 2), "z": PEN_UP_Z})
            else:
                px = cursor_x + float(item[0]) * scale
                py = origin_y - float(item[1]) * scale
                path.append({"x": round(px, 2), "y": round(py, 2), "z": 0})
        cursor_x += FONT_CHAR_W * scale
    path = decimate_to_max_points(path, max_points)
    return clamp_path(path)


def _motion_path_to_svg_d(path: list[dict[str, float]]) -> str:
    if not path:
        return ""
    parts: list[str] = []
    prev_pt: dict[str, float] | None = None
    pending_move = True
    for pt in path:
        # Pen-up = z > 0 (safe-height travel) or legacy consecutive duplicates.
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


def _path_bounds_with_margin(path: list[dict[str, float]], margin: float = 2.0) -> tuple[int, int]:
    if not path:
        return int(margin * 2), int(margin * 2)
    xs = [pt["x"] for pt in path]
    ys = [pt["y"] for pt in path]
    return max(int(max(xs) + margin), 1), max(int(max(ys) + margin), 1)


def text_to_svg_path(
    text: str,
    *,
    workspace_mm: dict[str, Any] | None = None,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, Any]:
    """Render ASCII text to an SVG path suitable for plotter preview."""
    rendered = render_text_task(text[:80], workspace_mm=workspace_mm, device_id=device_id, profile=profile)
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
    *,
    workspace_mm: dict[str, Any] | None = None,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, Any]:
    """Render a write_text intent into a motion task params dict with preview."""
    ws = resolve_workspace_mm(workspace_mm, device_id=device_id, profile=profile)
    path = text_to_path(text[:40])
    # GW-B1: text paths must pass workspace normalization like SVG paths do —
    # long text otherwise runs to 183mm+ and is dispatched out of bounds.
    path = _normalize_path_to_workspace(path, width=ws["x"], height=ws["y"])
    if passes > 1:
        path = apply_multi_pass(path, passes, offset_mm)
    if optimize:
        optimizer = PathOptimizer()
        path = optimizer.smooth(optimizer.compress(path))
    # GW-R3-7: multi_pass shifts +X and the optimizer may reshape after the
    # normalize-time check — re-assert bounds so a pass offset can never push
    # a point past the workspace and dispatch silently out of bounds.
    _assert_path_within_workspace(path, ws["x"], ws["y"], stage="text post-transform")
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f'text: "{text[:20]}"'),
        "point_count": len(path),
        "workspace_mm": ws,
    }


def _normalize_path_to_workspace(
    path: list[dict[str, float]], width: float = 100.0, height: float = 100.0, margin: float = 2.0
) -> list[dict[str, float]]:
    """Scale and translate a path so all points fit inside [0, width] x [0, height].

    Raises PathNormalizationError when any normalized point still falls outside
    the workspace (e.g. non-finite input coordinates).
    """
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
    # GW-B2: degenerate spans (pure horizontal/vertical lines) must still be
    # scaled on the non-degenerate axis — per-axis min instead of scale=1.0.
    scale_x = available_w / span_x if span_x > 0 else math.inf
    scale_y = available_h / span_y if span_y > 0 else math.inf
    scale = min(scale_x, scale_y, 1.0)
    origin_x = margin - min_x * scale
    origin_y = margin - min_y * scale
    normalized = [
        {"x": round(origin_x + pt["x"] * scale, 2), "y": round(origin_y + pt["y"] * scale, 2), "z": pt.get("z", 0)}
        for pt in path
    ]
    # GW-B2: post-translation assertion — reject instead of silently dispatching.
    _assert_path_within_workspace(normalized, width, height, stage="normalize")
    return normalized


def _assert_path_within_workspace(
    path: list[dict[str, float]],
    width: float = 100.0,
    height: float = 100.0,
    *,
    stage: str = "render",
) -> None:
    """GW-B2 / GW-R3-7: reject any point outside [0, width] x [0, height].

    Called both after normalization and again after post-normalize transforms
    (multi_pass shifts +X, optimizer may reshape) so a pass offset can no longer
    push coordinates past the workspace and dispatch silently out of bounds.
    """
    for idx, pt in enumerate(path):
        if not (0 <= pt["x"] <= width and 0 <= pt["y"] <= height):
            raise PathNormalizationError(
                f"{stage} point {idx} ({pt['x']},{pt['y']}) outside workspace {width}x{height}mm"
            )


def render_svg_task(
    d_string: str,
    passes: int = 1,
    offset_mm: float = 0.5,
    optimize: bool = True,
    *,
    workspace_mm: dict[str, Any] | None = None,
    device_id: str | None = None,
    profile: Any = None,
) -> dict[str, Any]:
    """Render an SVG path string into a motion task params dict with preview."""
    ws = resolve_workspace_mm(workspace_mm, device_id=device_id, profile=profile)
    path = svg_path_to_motion(d_string[:2000])
    path = _normalize_path_to_workspace(path, width=ws["x"], height=ws["y"])
    if passes > 1:
        path = apply_multi_pass(path, passes, offset_mm)
    if optimize:
        optimizer = PathOptimizer()
        path = optimizer.smooth(optimizer.compress(path))
    # GW-R3-7: re-assert bounds after multi_pass/optimizer so a pass offset can
    # never silently dispatch a point past the workspace (matches normalize dims).
    _assert_path_within_workspace(path, ws["x"], ws["y"], stage="svg post-transform")
    return {
        "path": path,
        "preview_svg": preview_svg(path, title=f"svg path — {len(path)} pts"),
        "point_count": len(path),
        "workspace_mm": ws,
    }


def precheck_draw_motion_path(
    d_string: str,
    *,
    workspace_mm: dict[str, Any] | None = None,
    device_id: str | None = None,
    profile: Any = None,
) -> str | None:
    """Return an error message when motion coordinates exceed workspace; else None."""
    if not d_string or not d_string.strip():
        return "empty svg path"
    ws = resolve_workspace_mm(workspace_mm, device_id=device_id, profile=profile)
    try:
        rendered = render_svg_task(d_string, workspace_mm=ws, device_id=device_id, profile=profile)
    except PathNormalizationError as exc:
        return str(exc)
    path = rendered.get("path") or []
    if not path:
        return "empty motion path"
    max_x, max_y, max_z = ws["x"], ws["y"], ws["z"]
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

    d_string = _motion_path_to_svg_d(path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#ccc"/>'
        f'<path d="{d_string}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="5" y="{height - 5}" font-size="10" fill="#888">{html.escape(title)} — {len(path)} pts</text>'
        f"</svg>"
    )
