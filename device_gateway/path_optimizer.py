"""Path optimization utilities for device drawing pipelines.

Provides polyline simplification, smoothing, and travel-move reordering
for motion paths produced by the device gateway. All point objects are
dictionaries with numeric keys ``x``, ``y``, ``z`` and optional metadata.

Pen-up / travel conventions
---------------------------
A "travel" move (pen up) is identified by one of:

1. A marker key ``"pen_up": True`` on the first point of the travel move.
   The marked point and any following points with ``z > 0`` are considered
   travel motion until the next drawing point with ``z == 0`` and no marker.
2. Consecutive points where ``z > 0`` (travel at safe height). A transition
   from ``z == 0`` to ``z > 0`` starts a travel move; a transition back ends it.

When segments are reordered, original travel sub-paths are discarded and
replaced by direct pen-up moves between segment endpoints.
"""

from __future__ import annotations

import math
from typing import Any


class PathOptimizer:
    """Simplify, smooth, and reorder device motion paths."""

    def compress(self, path: list[dict[str, Any]], tolerance: float = 0.5) -> list[dict[str, Any]]:
        """Simplify ``path`` using a Douglas-Peucker-like algorithm.

        Interior points whose perpendicular distance to the line between the
        segment endpoints is ``<= tolerance`` are removed. First and last
        points are always kept.
        """
        if len(path) <= 2:
            return path
        keep: set[int] = {0, len(path) - 1}
        stack: list[tuple[int, int]] = [(0, len(path) - 1)]
        while stack:
            start, end = stack.pop()
            if end <= start + 1:
                continue
            x1, y1 = path[start]["x"], path[start]["y"]
            x2, y2 = path[end]["x"], path[end]["y"]
            max_idx = start
            max_dist = -1.0
            for i in range(start + 1, end):
                d = self._point_to_line_distance(path[i]["x"], path[i]["y"], x1, y1, x2, y2)
                if d > max_dist:
                    max_dist = d
                    max_idx = i
            if max_dist > tolerance:
                keep.add(max_idx)
                stack.append((start, max_idx))
                stack.append((max_idx, end))
        return [path[i] for i in sorted(keep)]

    def smooth(self, path: list[dict[str, Any]], iterations: int = 2) -> list[dict[str, Any]]:
        """Smooth ``path`` with a 3-point weighted average on x/y.

        Weights are ``0.25 / 0.5 / 0.25``. Endpoints are preserved; ``z`` and
        any extra keys are copied unchanged.
        """
        if len(path) < 3 or iterations <= 0:
            return path
        result: list[dict[str, Any]] = [dict(p) for p in path]
        for _ in range(iterations):
            new_path: list[dict[str, Any]] = [result[0]]
            for i in range(1, len(result) - 1):
                prev_pt = result[i - 1]
                curr_pt = result[i]
                next_pt = result[i + 1]
                new_path.append(
                    {
                        **curr_pt,
                        "x": 0.25 * prev_pt["x"] + 0.5 * curr_pt["x"] + 0.25 * next_pt["x"],
                        "y": 0.25 * prev_pt["y"] + 0.5 * curr_pt["y"] + 0.25 * next_pt["y"],
                    }
                )
            new_path.append(result[-1])
            result = new_path
        return result

    def optimize_travel(self, path: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reorder drawing segments to reduce pen-up travel distance.

        Segments are split using the pen-up conventions documented in the
        module docstring. A greedy nearest-neighbor search chooses the next
        segment (and whether to reverse it) to minimize travel distance.
        """
        segments = self._split_by_pen_up(path)
        if len(segments) <= 1:
            return path
        ordered = self._reorder_segments_greedy(segments)
        result: list[dict[str, Any]] = []
        for i, seg in enumerate(ordered):
            if i > 0 and result:
                prev = result[-1]
                first = seg[0]
                result.append({**first, "z": prev.get("z", 0.0), "pen_up": True})
            result.extend(seg)
        return result

    def _split_by_pen_up(self, path: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Split ``path`` into drawing segments separated by travel moves."""
        segments: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        in_travel = False
        for pt in path:
            z = float(pt.get("z", 0.0))
            has_pen_up = bool(pt.get("pen_up"))
            if has_pen_up:
                in_travel = True
                if current:
                    segments.append(current)
                    current = []
            elif in_travel:
                if z == 0:
                    in_travel = False
                    current.append(dict(pt))
            elif z > 0:
                in_travel = True
                if current:
                    segments.append(current)
                    current = []
            else:
                current.append(dict(pt))
        if current:
            segments.append(current)
        return segments

    def _reorder_segments_greedy(self, segments: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """Greedy nearest-neighbor ordering with optional segment reversal."""
        if not segments:
            return []
        remaining: list[dict[str, Any]] = [{"seg": list(seg), "visited": False} for seg in segments]
        ordered: list[list[dict[str, Any]]] = []
        current_x = float(remaining[0]["seg"][-1]["x"])
        current_y = float(remaining[0]["seg"][-1]["y"])
        remaining[0]["visited"] = True
        ordered.append(remaining[0]["seg"])
        while len(ordered) < len(segments):
            best_idx = -1
            best_cost = float("inf")
            best_reversed = False
            for i, item in enumerate(remaining):
                if item["visited"]:
                    continue
                seg = item["seg"]
                cost_normal = self._dist(current_x, current_y, seg[0]["x"], seg[0]["y"])
                cost_reversed = self._dist(current_x, current_y, seg[-1]["x"], seg[-1]["y"])
                if cost_reversed < cost_normal and cost_reversed < best_cost:
                    best_cost = cost_reversed
                    best_idx = i
                    best_reversed = True
                elif cost_normal < best_cost:
                    best_cost = cost_normal
                    best_idx = i
                    best_reversed = False
            item = remaining[best_idx]
            item["visited"] = True
            seg = list(item["seg"])
            if best_reversed:
                seg.reverse()
            ordered.append(seg)
            current_x = float(seg[-1]["x"])
            current_y = float(seg[-1]["y"])
        return ordered

    @staticmethod
    def _point_to_line_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        """Perpendicular distance from point (px, py) to line (x1,y1)-(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    @staticmethod
    def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
        """Euclidean distance between two 2-D points."""
        return math.hypot(x2 - x1, y2 - y1)


def apply_multi_pass(base_path: list[dict[str, Any]], passes: int, offset_mm: float) -> list[dict[str, Any]]:
    """Generate ``passes`` copies of ``base_path`` offset along the X axis.

    The first pass is unchanged; pass ``n`` (0-indexed) is shifted by
    ``n * offset_mm`` in the positive X direction. Extra point keys are
    preserved.
    """
    if passes <= 1:
        return [dict(p) for p in base_path]
    result: list[dict[str, Any]] = []
    for n in range(passes):
        shift = n * offset_mm
        for pt in base_path:
            new_pt = dict(pt)
            new_pt["x"] = round(float(pt.get("x", 0.0)) + shift, 2)
            result.append(new_pt)
    return result
