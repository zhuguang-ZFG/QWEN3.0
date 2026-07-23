"""Point-count decimation for motion paths (pen-up aware).

Reuses the Douglas-Peucker simplifier from ``xiaozhi_drawing.path_optimizer``
to shrink a stroke-font polyline under the device point budget
(``MAX_PATH_POINTS``) instead of silently truncating trailing glyphs
(clamp_path's ``path[:max_points]`` behaviour — forbidden silent downgrade).

Strategy: split the flat path at pen-up markers (``z > 0``), simplify each
drawing stroke independently so strokes are never merged across a travel
move, then escalate tolerance until the total fits. This lets a path like
``'写'*40`` (280 pts of '?' glyphs) shrink to <= budget with every glyph
preserved, instead of clamp_path dropping the trailing ~12 glyphs.

Genuinely oversized text (hundreds of chars) can still exceed the budget
even after every stroke collapses to its endpoints — that residual case is
left to clamp_path's hard cap, the pre-existing contract for such input.
"""

from __future__ import annotations

from typing import Any

from xiaozhi_drawing.path_optimizer import _simplify_points

# Tolerance escalation: start sub-millimetre, double until the path fits.
# The final iteration collapses every stroke to its endpoints, so the loop
# is guaranteed to terminate at the theoretical minimum point count.
_START_TOLERANCE = 0.25
_MAX_TOLERANCE = 1.0e6


def _split_strokes(path: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group the path into strokes: optional pen-up marker + its draw points."""
    strokes: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for pt in path:
        if float(pt.get("z", 0.0)) > 0:
            if current:
                strokes.append(current)
            current = [pt]
        else:
            current.append(pt)
    if current:
        strokes.append(current)
    return strokes


def _simplify_stroke(stroke: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
    """Douglas-Peucker on the stroke's draw points; pen-up marker untouched."""
    if len(stroke) <= 2:
        return stroke
    markers = [pt for pt in stroke if float(pt.get("z", 0.0)) > 0]
    draws = [pt for pt in stroke if float(pt.get("z", 0.0)) <= 0]
    if len(draws) <= 2:
        return stroke
    kept = _simplify_points([(pt["x"], pt["y"]) for pt in draws], tolerance)
    kept_set = set(kept)
    simplified_draws: list[dict[str, Any]] = []
    for pt in draws:
        key = (pt["x"], pt["y"])
        if key in kept_set:
            kept_set.discard(key)  # keep first occurrence only (dup coords)
            simplified_draws.append(pt)
    return markers + simplified_draws


def decimate_to_max_points(
    path: list[dict[str, Any]],
    max_points: int,
) -> list[dict[str, Any]]:
    """Return ``path`` simplified toward ``max_points`` points.

    Escalates Douglas-Peucker tolerance until the path fits the budget. If
    even the fully collapsed path (endpoints only per stroke) still exceeds
    ``max_points`` — genuinely oversized text — the best-effort collapsed
    result is returned and clamp_path applies the final hard cap.
    """
    if len(path) <= max_points:
        return path
    strokes = _split_strokes(path)
    tolerance = _START_TOLERANCE
    result = path
    while tolerance <= _MAX_TOLERANCE:
        result = [pt for stroke in strokes for pt in _simplify_stroke(stroke, tolerance)]
        if len(result) <= max_points:
            return result
        tolerance *= 2.0
    return result
