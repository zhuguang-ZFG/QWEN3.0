"""W1 regression: run_path workspace bounds must be enforced with the resolved profile.

The 2026-07-20 review found _validate_params_or_error called
validate_capability_params without the resolved profile, so
profile_limit_error(params, None) short-circuited and client-supplied
run_path coordinates were only bounded by the ±500 static limit — 3x the
100mm default workspace and 8x the 60mm conservative fallback.
"""

from __future__ import annotations

import pytest

from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests


@pytest.fixture(autouse=True)
def _reset_store():
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


def _run_path_task(points: list[dict], feed: float = 500) -> dict:
    return {
        "capability": "run_path",
        "params": {"path": points, "feed": feed, "source_capability": "run_path"},
        "source": "api",
    }


@pytest.mark.asyncio
async def test_run_path_outside_workspace_is_rejected():
    # Unknown device resolves the conservative profile (60mm workspace);
    # x=300 passes the old ±500 static gate but must fail the profile gate.
    task = await project_to_motion_task_async("dev-w1-oob", _run_path_task([{"x": 300, "y": 10, "z": 0}]))
    assert task.get("error"), "out-of-workspace run_path must be rejected"
    assert task["error"]["code"] == "E_BAD_PARAMS"


@pytest.mark.asyncio
async def test_run_path_negative_coordinate_is_rejected():
    task = await project_to_motion_task_async("dev-w1-neg", _run_path_task([{"x": -5, "y": 10, "z": 0}]))
    assert task.get("error"), "negative coordinate must be rejected"


@pytest.mark.asyncio
async def test_run_path_inside_workspace_is_accepted():
    task = await project_to_motion_task_async(
        "dev-w1-ok", _run_path_task([{"x": 10, "y": 10, "z": 0}, {"x": 50, "y": 50, "z": 0}])
    )
    assert "error" not in task
    assert task["capability"] == "run_path"


@pytest.mark.asyncio
async def test_run_path_over_limit_feed_is_clamped_not_rejected():
    # Conservative profile max_feed=600; overrun clamps (matching
    # apply_profile_constraints semantics) instead of hard-rejecting.
    task = await project_to_motion_task_async("dev-w1-feed", _run_path_task([{"x": 10, "y": 10, "z": 0}], feed=1500))
    assert "error" not in task
    assert task["params"]["feed"] <= 600
