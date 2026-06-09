"""M4: Simulator — deterministic motion simulation metrics."""

from __future__ import annotations

import math

import pytest

from device_intelligence.schemas import DeviceProfile, TaskPlan
from device_intelligence.simulator import SimResult, simulate_motion


def _square_plan(side_mm: float = 10.0) -> TaskPlan:
    """A simple square path: 4 sides, pen-down."""
    path = [
        {"x": 0, "y": 0, "z": 0},
        {"x": side_mm, "y": 0, "z": 0},
        {"x": side_mm, "y": side_mm, "z": 0},
        {"x": 0, "y": side_mm, "z": 0},
        {"x": 0, "y": 0, "z": 0},
    ]
    return TaskPlan(
        plan_id="sim-001",
        device_id="dev-sim",
        capability="run_path",
        params={"path": path, "feed": 600},
    )


def _pen_up_plan() -> TaskPlan:
    """Path with a pen-up traverse (z > 0 gap between segments)."""
    path = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 5},  # pen up
        {"x": 50, "y": 0, "z": 5},  # traverse
        {"x": 50, "y": 0, "z": 0},  # pen down
        {"x": 50, "y": 10, "z": 0},
    ]
    return TaskPlan(
        plan_id="sim-002",
        device_id="dev-sim",
        capability="run_path",
        params={"path": path, "feed": 600},
    )


class TestSimulatorDrawDistance:
    """Draw distance = sum of XY distances for pen-down segments."""

    def test_square_draw_distance(self) -> None:
        result = simulate_motion(_square_plan(side_mm=10.0))
        assert isinstance(result, SimResult)
        assert math.isclose(result.draw_distance_mm, 40.0, abs_tol=0.01)

    def test_square_larger(self) -> None:
        result = simulate_motion(_square_plan(side_mm=25.0))
        assert math.isclose(result.draw_distance_mm, 100.0, abs_tol=0.01)

    def test_no_path_zero_distance(self) -> None:
        plan = TaskPlan(
            plan_id="sim-empty",
            device_id="dev-sim",
            capability="home",
            params={},
        )
        result = simulate_motion(plan)
        assert result.draw_distance_mm == 0.0


class TestSimulatorPenUpDistance:
    """Pen-up distance = XY distance traversed while z > 0."""

    def test_square_no_pen_up(self) -> None:
        result = simulate_motion(_square_plan())
        assert result.pen_up_distance_mm == 0.0

    def test_pen_up_traverse(self) -> None:
        result = simulate_motion(_pen_up_plan())
        # Pen-up segment: (10,0,5) → (50,0,5) = 40mm
        assert math.isclose(result.pen_up_distance_mm, 40.0, abs_tol=0.01)


class TestSimulatorRuntime:
    """Estimated runtime = total distance / feed * 60 (seconds)."""

    def test_square_runtime(self) -> None:
        result = simulate_motion(_square_plan(side_mm=10.0))
        # 40mm at 600mm/min = 40/600*60 = 4.0 seconds
        assert math.isclose(result.estimated_runtime_sec, 4.0, abs_tol=0.01)

    def test_runtime_includes_pen_up(self) -> None:
        result = simulate_motion(_pen_up_plan())
        # draw: 10 + 40 + 10 = 60mm; pen_up: 40mm; total=100mm
        # 100/600*60 = 10.0 sec
        total = result.draw_distance_mm + result.pen_up_distance_mm
        expected = total / 600.0 * 60.0
        assert math.isclose(result.estimated_runtime_sec, expected, abs_tol=0.01)

    def test_default_feed_when_missing(self) -> None:
        plan = TaskPlan(
            plan_id="sim-nofeed",
            device_id="dev-sim",
            capability="run_path",
            params={"path": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 0}]},
        )
        result = simulate_motion(plan)
        # default feed 600, distance 10mm → 10/600*60 = 1.0
        assert math.isclose(result.estimated_runtime_sec, 1.0, abs_tol=0.01)


class TestSimulatorRiskScore:
    """Risk score 0.0–1.0 based on workspace usage and path complexity."""

    def test_small_path_low_risk(self) -> None:
        profile = DeviceProfile(profile_id="p1", model="test", workspace_mm={"x": 100, "y": 100, "z": 20})
        result = simulate_motion(_square_plan(side_mm=5.0), profile=profile)
        assert 0.0 <= result.risk_score <= 0.3

    def test_large_path_higher_risk(self) -> None:
        profile = DeviceProfile(profile_id="p1", model="test", workspace_mm={"x": 100, "y": 100, "z": 20})
        small = simulate_motion(_square_plan(side_mm=5.0), profile=profile)
        large = simulate_motion(_square_plan(side_mm=45.0), profile=profile)
        assert large.risk_score > small.risk_score

    def test_no_profile_default_risk(self) -> None:
        result = simulate_motion(_square_plan())
        assert 0.0 <= result.risk_score <= 1.0

    def test_many_points_higher_risk(self) -> None:
        profile = DeviceProfile(profile_id="p1", model="test", workspace_mm={"x": 100, "y": 100, "z": 20})
        # Dense path with many points
        dense_path = [{"x": i, "y": 0, "z": 0} for i in range(50)]
        dense_plan = TaskPlan(
            plan_id="sim-dense", device_id="dev-sim",
            capability="run_path", params={"path": dense_path, "feed": 600},
        )
        sparse_path = [{"x": 0, "y": 0, "z": 0}, {"x": 49, "y": 0, "z": 0}]
        sparse_plan = TaskPlan(
            plan_id="sim-sparse", device_id="dev-sim",
            capability="run_path", params={"path": sparse_path, "feed": 600},
        )
        dense_r = simulate_motion(dense_plan, profile=profile)
        sparse_r = simulate_motion(sparse_plan, profile=profile)
        assert dense_r.risk_score >= sparse_r.risk_score


class TestSimResultStructure:
    """SimResult is a frozen dataclass with expected fields."""

    def test_fields(self) -> None:
        result = simulate_motion(_square_plan())
        assert hasattr(result, "draw_distance_mm")
        assert hasattr(result, "pen_up_distance_mm")
        assert hasattr(result, "estimated_runtime_sec")
        assert hasattr(result, "risk_score")
        assert hasattr(result, "warnings")

    def test_warnings_is_list(self) -> None:
        result = simulate_motion(_square_plan())
        assert isinstance(result.warnings, list)

    def test_to_dict(self) -> None:
        result = simulate_motion(_square_plan())
        d = result.to_dict()
        assert "draw_distance_mm" in d
        assert "risk_score" in d
