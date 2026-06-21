"""Trace 1px skeleton pixels into open polylines for pen-plotter SVG."""

from __future__ import annotations

import numpy as np

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cv2 = None

Pixel = tuple[int, int]  # (row, col)


def trace_skeleton_polylines(skeleton: np.ndarray, *, min_points: int = 2) -> list[list[tuple[int, int]]]:
    """Walk the skeleton graph and return polylines as (x, y) coordinates."""
    skel_set = _active_pixels(skeleton)
    if not skel_set:
        return []

    junctions = {pixel for pixel in skel_set if len(_neighbors8(pixel, skel_set)) >= 3}
    endpoints = [pixel for pixel in skel_set if len(_neighbors8(pixel, skel_set)) == 1]
    visited: set[Pixel] = set()
    paths: list[list[Pixel]] = []

    for start in endpoints or sorted(skel_set)[:20]:
        if start in visited:
            continue
        path = _walk_from(start, skel_set, junctions, visited)
        if len(path) >= min_points:
            paths.append(path)

    for junction in sorted(junctions):
        if junction in visited:
            continue
        path = _walk_from(junction, skel_set, junctions, visited)
        if len(path) >= min_points:
            paths.append(path)

    paths.extend(_walk_remaining(skel_set, visited, min_points))
    return [[(col, row) for row, col in path] for path in paths]


def polylines_to_svg_paths(
    polylines: list[list[tuple[int, int]]],
    *,
    simplify_epsilon: float,
    min_arc_length: float,
) -> list[str]:
    """Simplify polylines and emit open SVG path strings."""
    if cv2 is None:
        raise RuntimeError("OpenCV is not installed")

    svg_paths: list[str] = []
    for points in polylines:
        if len(points) < 2:
            continue
        contour = np.array(points, dtype=np.int32).reshape(-1, 1, 2)
        if cv2.arcLength(contour, False) < min_arc_length:
            continue
        approx = cv2.approxPolyDP(contour, simplify_epsilon, False)
        if len(approx) < 2:
            continue
        parts = [f"M {approx[0][0][0]} {approx[0][0][1]}"]
        for point in approx[1:]:
            parts.append(f"L {point[0][0]} {point[0][1]}")
        svg_paths.append(" ".join(parts))
    return svg_paths


def _active_pixels(skeleton: np.ndarray) -> set[Pixel]:
    rows, cols = np.where(skeleton > 0)
    return {(int(row), int(col)) for row, col in zip(rows, cols, strict=True)}


def _neighbors8(pixel: Pixel, skel_set: set[Pixel]) -> list[Pixel]:
    row, col = pixel
    neighbors: list[Pixel] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nxt = (row + dr, col + dc)
            if nxt in skel_set:
                neighbors.append(nxt)
    return neighbors


def _walk_from(
    start: Pixel,
    skel_set: set[Pixel],
    junctions: set[Pixel],
    visited: set[Pixel],
) -> list[Pixel]:
    path = [start]
    visited.add(start)
    current = start
    while True:
        candidates = [n for n in _neighbors8(current, skel_set) if n not in visited]
        if not candidates:
            break
        nxt = _pick_next(current, path, candidates, junctions)
        path.append(nxt)
        visited.add(nxt)
        current = nxt
    return path


def _pick_next(
    current: Pixel,
    path: list[Pixel],
    candidates: list[Pixel],
    junctions: set[Pixel],
) -> Pixel:
    if current in junctions and len(path) >= 2:
        prev = path[-2]
        dr = current[0] - prev[0]
        dc = current[1] - prev[1]
        best_dot = -999
        best: Pixel | None = None
        for candidate in candidates:
            ndr = candidate[0] - current[0]
            ndc = candidate[1] - current[1]
            dot = dr * ndr + dc * ndc
            if dot > best_dot:
                best_dot = dot
                best = candidate
        if best is not None:
            return best
    return min(candidates, key=lambda p: (p[0] - current[0]) ** 2 + (p[1] - current[1]) ** 2)


def _walk_remaining(skel_set: set[Pixel], visited: set[Pixel], min_points: int) -> list[list[Pixel]]:
    remaining = skel_set - visited
    paths: list[list[Pixel]] = []
    while remaining:
        start = min(remaining)
        path = [start]
        visited.add(start)
        remaining.discard(start)
        current = start
        while True:
            candidates = [n for n in _neighbors8(current, skel_set) if n not in visited]
            if not candidates:
                break
            nxt = min(candidates, key=lambda p: (p[0] - current[0]) ** 2 + (p[1] - current[1]) ** 2)
            path.append(nxt)
            visited.add(nxt)
            remaining.discard(nxt)
            current = nxt
        if len(path) >= min_points:
            paths.append(path)
    return paths
