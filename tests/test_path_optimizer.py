"""Tests for device_gateway.path_optimizer."""

from __future__ import annotations

import math
from typing import Any

import pytest

from device_gateway.path_optimizer import PathOptimizer, apply_multi_pass


@pytest.fixture
def optimizer() -> PathOptimizer:
    return PathOptimizer()


def test_compress_keeps_first_and_last_points(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 1, "y": 0, "z": 0},
        {"x": 2, "y": 0, "z": 0},
        {"x": 3, "y": 0, "z": 0},
    ]
    compressed = optimizer.compress(path, tolerance=0.5)
    assert compressed[0] == path[0]
    assert compressed[-1] == path[-1]


def test_compress_removes_collinear_points(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 1, "y": 0, "z": 0},
        {"x": 2, "y": 0, "z": 0},
        {"x": 3, "y": 0, "z": 0},
        {"x": 4, "y": 0, "z": 0},
    ]
    compressed = optimizer.compress(path, tolerance=0.5)
    assert len(compressed) == 2


def test_compress_preserves_high_deviation_points(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 1, "y": 2, "z": 0},
        {"x": 2, "y": 0, "z": 0},
    ]
    compressed = optimizer.compress(path, tolerance=0.5)
    assert len(compressed) == 3


def test_smooth_preserves_endpoints_and_z(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 2, "y": 0, "z": 0},
        {"x": 4, "y": 0, "z": 0},
    ]
    smoothed = optimizer.smooth(path, iterations=1)
    assert smoothed[0] == path[0]
    assert smoothed[-1] == path[-1]
    assert all(pt["z"] == 0 for pt in smoothed)


def test_smooth_moves_points_toward_neighbors(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 2, "y": 1, "z": 0},
        {"x": 4, "y": 0, "z": 0},
    ]
    smoothed = optimizer.smooth(path, iterations=1)
    # Interior point is pulled toward the line between neighbors.
    assert smoothed[1]["y"] < path[1]["y"]
    assert smoothed[1]["x"] == pytest.approx(2.0)


def _total_distance(path: list[dict[str, Any]]) -> float:
    return sum(
        math.hypot(path[i]["x"] - path[i - 1]["x"], path[i]["y"] - path[i - 1]["y"])
        for i in range(1, len(path))
    )


def test_optimize_travel_reduces_segment_to_segment_distance(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0, "pen_up": True},
        {"x": 20, "y": 0, "z": 0},
        {"x": 30, "y": 0, "z": 0},
        {"x": 30, "y": 0, "z": 0, "pen_up": True},
        {"x": 5, "y": 5, "z": 0},
        {"x": 15, "y": 5, "z": 0},
    ]
    optimized = optimizer.optimize_travel(path)
    assert _total_distance(optimized) < _total_distance(path)


def test_optimize_travel_keeps_single_segment_unchanged(optimizer: PathOptimizer) -> None:
    path: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
        {"x": 10, "y": 10, "z": 0},
    ]
    optimized = optimizer.optimize_travel(path)
    assert optimized == path


def test_apply_multi_pass_generates_passes_copies_with_offset() -> None:
    base: list[dict[str, Any]] = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
    ]
    result = apply_multi_pass(base, passes=3, offset_mm=2.0)
    assert len(result) == 6
    assert result[0]["x"] == 0
    assert result[1]["x"] == 10
    assert result[2]["x"] == 2
    assert result[3]["x"] == 12
    assert result[4]["x"] == 4
    assert result[5]["x"] == 14
    assert all(pt["z"] == 0 for pt in result)


def test_apply_multi_pass_single_pass_returns_copy() -> None:
    base: list[dict[str, Any]] = [{"x": 1, "y": 2, "z": 0}]
    result = apply_multi_pass(base, passes=1, offset_mm=1.0)
    assert result == base
    assert result is not base
