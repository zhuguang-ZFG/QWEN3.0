"""Spur pruning for single-pixel skeleton images.

Skeletonization of noisy or gradient-heavy images often leaves short spurs:
tiny branches that grow out of junctions and end in degree-1 pixels. These
produce unwanted pen-plotter strokes. This module removes them iteratively
before polyline tracing.
"""

from __future__ import annotations

import numpy as np

Pixel = tuple[int, int]  # (row, col)


def _active_pixels(skeleton: np.ndarray) -> set[Pixel]:
    rows, cols = np.where(skeleton > 0)
    return {(int(row), int(col)) for row, col in zip(rows, cols, strict=True)}


def _neighbors8(pixel: Pixel, active: set[Pixel]) -> list[Pixel]:
    row, col = pixel
    neighbors: list[Pixel] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nxt = (row + dr, col + dc)
            if nxt in active:
                neighbors.append(nxt)
    return neighbors


def _walk_to_junction(
    start: Pixel,
    active: set[Pixel],
) -> tuple[list[Pixel], Pixel | None]:
    """Walk from an endpoint until the next junction, endpoint, or dead end.

    Returns (path_without_terminal_junction, terminal_pixel_or_none). The
    terminal pixel is a junction if the walk ended because multiple unvisited
    branches were available, otherwise None.
    """
    path: list[Pixel] = [start]
    prev: Pixel | None = None
    current = start
    while True:
        candidates = [n for n in _neighbors8(current, active) if n != prev]
        if not candidates:
            # Dead end or endpoint: not a spur anchored at a junction.
            return path, None
        if len(candidates) > 1:
            # Reached a junction; current itself is the junction.
            return path, current
        nxt = candidates[0]
        path.append(nxt)
        prev, current = current, nxt


def prune_skeleton_spurs(skeleton: np.ndarray, spur_length_threshold: int = 10) -> np.ndarray:
    """Iteratively remove short spurs from a single-pixel skeleton.

    A spur is a degree-1 endpoint branch that reaches a junction in fewer than
    ``spur_length_threshold`` pixels. Removal is repeated because pruning one
    spur can turn a former junction into a new endpoint spur.

    Args:
        skeleton: Binary image with active skeleton pixels > 0.
        spur_length_threshold: Maximum branch length (in pixels) to prune.

    Returns:
        New binary image with spurs removed.
    """
    if skeleton.size == 0 or spur_length_threshold <= 0:
        return skeleton.copy()

    active = _active_pixels(skeleton)
    if not active:
        return skeleton.copy()

    changed = True
    while changed:
        changed = False
        degrees = {pixel: len(_neighbors8(pixel, active)) for pixel in active}
        endpoints = {pixel for pixel, degree in degrees.items() if degree == 1}
        for endpoint in endpoints:
            if endpoint not in active:
                continue
            path, junction = _walk_to_junction(endpoint, active)
            if junction is not None and len(path) < spur_length_threshold:
                # Remove the spur pixels but keep the junction itself.
                active.difference_update(path)
                changed = True

    result = np.zeros_like(skeleton)
    if active:
        rows, cols = zip(*active, strict=True)
        result[rows, cols] = skeleton[rows, cols]
    return result
