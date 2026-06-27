"""Stroke ordering for pen-plotter SVG paths.

Reduces pen travel between open polylines by greedily picking the nearest
unvisited stroke, allowing each stroke to be drawn in either direction.
"""

from __future__ import annotations

import math

Point = tuple[int, int]
Polyline = list[Point]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _endpoints(polyline: Polyline) -> tuple[Point, Point]:
    return polyline[0], polyline[-1]


def reorder_polylines_nearest_neighbor(polylines: list[Polyline]) -> list[Polyline]:
    """Reorder polylines to minimize travel distance using greedy nearest neighbor.

    Each polyline may be reversed if its endpoint is closer to the current
    position than its start. The first polyline is kept in its original
    orientation to keep output deterministic.

    Args:
        polylines: List of polylines as [(x, y), ...].

    Returns:
        Reordered list; may be reversed in place for selected strokes.
    """
    if len(polylines) < 2:
        return list(polylines)

    remaining: list[Polyline] = [list(p) for p in polylines]
    ordered: list[Polyline] = [remaining.pop(0)]
    current_pos = _endpoints(ordered[0])[1]

    while remaining:
        best_index = 0
        best_dist = float("inf")
        best_reversed = False
        for index, polyline in enumerate(remaining):
            start, end = _endpoints(polyline)
            d_start = _distance(current_pos, start)
            d_end = _distance(current_pos, end)
            if d_start < best_dist:
                best_dist = d_start
                best_index = index
                best_reversed = False
            if d_end < best_dist:
                best_dist = d_end
                best_index = index
                best_reversed = True

        chosen = remaining.pop(best_index)
        if best_reversed:
            chosen.reverse()
        ordered.append(chosen)
        current_pos = _endpoints(chosen)[1]

    return ordered
