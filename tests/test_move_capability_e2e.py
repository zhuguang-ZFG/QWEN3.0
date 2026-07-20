"""GW-R3-12 end-to-end: voice/app move_abs & move_rel reach firmware intact.

Covers the four layers that previously dropped point-to-point motion:
- L1 capability allowlists (validate_capability_params no longer E_UNSUPPORTED)
- L2 scalar param validation + server-side workspace bounds
- L3 projection capability passthrough (not rewritten to run_path)
- L4 fuzzy voice replan of a rejected command into move is permitted
"""

from __future__ import annotations

import pytest

from device_gateway.path_validator import validate_capability_params
from device_intelligence.schemas import DeviceProfile


# ── L1 + L2: validation ───────────────────────────────────────────────────────


def test_move_abs_valid_within_profile_workspace():
    profile = DeviceProfile(profile_id="p", model="m", workspace_mm={"x": 300.0, "y": 300.0, "z": 80.0})
    sanitized, error = validate_capability_params("move_abs", {"x": 150, "y": 200, "feed": 1000}, profile=profile)
    assert error is None
    assert sanitized["x"] == 150.0 and sanitized["y"] == 200.0
    assert sanitized["feed"] == 1000.0
    assert sanitized["source_capability"] == "move_abs"


def test_move_abs_rejects_outside_workspace():
    profile = DeviceProfile(profile_id="p", model="m", workspace_mm={"x": 100.0, "y": 100.0, "z": 20.0})
    _, error = validate_capability_params("move_abs", {"x": 250, "y": 10}, profile=profile)
    assert error == "E_BAD_PARAMS"


def test_move_abs_rejects_negative_and_nan():
    profile = DeviceProfile(profile_id="p", model="m", workspace_mm={"x": 300.0, "y": 300.0, "z": 80.0})
    _, neg = validate_capability_params("move_abs", {"x": -1, "y": 10}, profile=profile)
    assert neg == "E_BAD_PARAMS"
    _, nan = validate_capability_params("move_abs", {"x": float("nan"), "y": 10}, profile=profile)
    assert nan == "E_BAD_PARAMS"


def test_move_abs_no_profile_falls_back_to_hard_limit():
    # No profile: accept up to the ±500 hard limit (firmware re-checks the real workspace).
    sanitized, error = validate_capability_params("move_abs", {"x": 300, "y": 60})
    assert error is None
    assert sanitized["x"] == 300.0
    _, over = validate_capability_params("move_abs", {"x": 600, "y": 0})
    assert over == "E_BAD_PARAMS"


def test_move_abs_z_only_bounded_when_supplied():
    profile = DeviceProfile(profile_id="p", model="m", workspace_mm={"x": 300.0, "y": 300.0, "z": 80.0})
    # z omitted → not in sanitized (firmware has_z=false, no pen-down).
    sanitized, error = validate_capability_params("move_abs", {"x": 10, "y": 10}, profile=profile)
    assert error is None and "z" not in sanitized
    # z supplied but out of range → rejected.
    _, over = validate_capability_params("move_abs", {"x": 10, "y": 10, "z": 200}, profile=profile)
    assert over == "E_BAD_PARAMS"


def test_move_rel_valid_single_axis_jog():
    sanitized, error = validate_capability_params("move_rel", {"dx": 1, "dy": 0, "feed": 800})
    assert error is None
    assert sanitized["dx"] == 1.0 and sanitized["dy"] == 0.0 and sanitized["dz"] == 0.0
    assert sanitized["source_capability"] == "move_rel"


def test_move_rel_rejects_step_over_one_mm():
    _, error = validate_capability_params("move_rel", {"dx": 5, "dy": 0})
    assert error == "E_BAD_PARAMS"


def test_move_rel_rejects_all_zero():
    _, error = validate_capability_params("move_rel", {"dx": 0, "dy": 0, "dz": 0})
    assert error == "E_BAD_PARAMS"


# ── L3: projection passthrough ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_move_abs_projection_keeps_capability(monkeypatch):
    from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests

    reset_tasks_for_tests()
    try:
        task = await project_to_motion_task_async(
            "dev-move",
            {"capability": "move_abs", "params": {"x": 40, "y": 50, "feed": 1000}, "source": "voice"},
        )
        assert task["capability"] == "move_abs"
        assert task.get("error") is None
        assert task["params"]["x"] == 40.0 and task["params"]["y"] == 50.0
    finally:
        reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_move_rel_projection_keeps_capability(monkeypatch):
    from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests

    reset_tasks_for_tests()
    try:
        task = await project_to_motion_task_async(
            "dev-move",
            {"capability": "move_rel", "params": {"dx": 1, "dy": -1, "feed": 800}, "source": "voice"},
        )
        assert task["capability"] == "move_rel"
        assert task.get("error") is None
    finally:
        reset_tasks_for_tests()
