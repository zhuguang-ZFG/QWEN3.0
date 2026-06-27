"""Tests for stroke/path ordering utilities."""

from __future__ import annotations

import pytest

import numpy as np

from xiaozhi_drawing.path_ordering import reorder_polylines_nearest_neighbor
from xiaozhi_drawing.svg_converter import _extract_svg_paths

cv2 = pytest.importorskip("cv2")


class TestReorderPolylinesNearestNeighbor:
    def test_empty_returns_empty(self):
        assert reorder_polylines_nearest_neighbor([]) == []

    def test_single_polyline_returns_unchanged(self):
        polyline = [(0, 0), (10, 0)]
        result = reorder_polylines_nearest_neighbor([polyline])
        assert result == [polyline]

    def test_reorders_two_horizontal_lines(self):
        # Top line first, then bottom line far away. Reordering picks the bottom
        # line and reverses it so its (10,20) endpoint connects to top's end.
        top = [(0, 0), (10, 0)]
        bottom = [(0, 20), (10, 20)]
        result = reorder_polylines_nearest_neighbor([top, bottom])
        assert result[0] == top
        assert result[1] == [(10, 20), (0, 20)]

    def test_reverses_when_end_is_closer(self):
        # After top (0,0)->(10,0), the closest point of the next stroke is its
        # end (10,20), so it should be reversed to start there.
        top = [(0, 0), (10, 0)]
        bottom = [(0, 20), (10, 20)]
        result = reorder_polylines_nearest_neighbor([bottom, top])
        # Starts with bottom. Current pos after bottom = (10,20) if not reversed
        # or (0,20) if reversed. top has endpoints (0,0),(10,0). From bottom
        # as-is, distance to (10,0)=20, to (0,0)=22 -> top as-is.
        # So no reversal expected in this specific geometry.
        # Use a clearer geometry: line A from (0,0)->(10,0); line B from
        # (20,0)->(30,0). After A, pos=(10,0). B start (20,0) distance 10,
        # B end (30,0) distance 20 -> B stays as-is. Not helpful.
        # Geometry where end is closer:
        a = [(0, 0), (10, 0)]
        b = [(20, 0), (10, 0)]  # b's end is exactly at a's end
        result = reorder_polylines_nearest_neighbor([a, b])
        assert result[0] == a
        # After a, pos=(10,0). b start (20,0) dist 10, b end (10,0) dist 0
        # -> b reversed so it starts at (10,0).
        assert result[1] == [(10, 0), (20, 0)]

    def test_keeps_first_polyline_fixed(self):
        first = [(100, 100), (110, 100)]
        second = [(0, 0), (10, 0)]
        third = [(105, 105), (115, 105)]
        result = reorder_polylines_nearest_neighbor([first, second, third])
        assert result[0] == first
        # After first, closest should be third, not second.
        assert result[1] == third


class TestExtractSvgPathsReorder:
    def test_reorder_strokes_reduces_travel(self):
        # Three short horizontal strokes. Reordering should not change the set of
        # strokes and should not produce a longer total travel distance than raw.
        binary = np.zeros((20, 40), dtype=np.uint8)
        binary[4, 2:8] = 255  # A
        binary[10, 2:8] = 255  # B
        binary[6, 20:30] = 255  # C
        paths_raw, _ = _extract_svg_paths(binary, 1.0, 1, skeletonize=True, reorder_strokes=False)
        paths_ordered, _ = _extract_svg_paths(binary, 1.0, 1, skeletonize=True, reorder_strokes=True)
        assert len(paths_raw) == len(paths_ordered) == 3

        def _parse_start(path: str) -> tuple[float, float]:
            parts = path.split()
            return float(parts[1]), float(parts[2])

        def _travel(paths: list[str]) -> float:
            total = 0.0
            for prev, curr in zip(paths, paths[1:], strict=False):
                x1, y1 = _parse_start(prev)
                x2, y2 = _parse_start(curr)
                total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            return total

        assert _travel(paths_ordered) <= _travel(paths_raw) + 1e-6
