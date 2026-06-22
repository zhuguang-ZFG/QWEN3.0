"""Profile constraint tests."""

from unittest.mock import AsyncMock

from device_gateway.device_route_memory import reset_route_memory_for_tests
from device_gateway.device_simplification_logger import record_simplification
from device_gateway.profiles import (
    CONSERVATIVE_MAX_PATH_POINTS,
    apply_profile_constraints,
    register_profile,
    reset_profiles_for_tests,
    resolve_profile,
)
from device_intelligence.schemas import DeviceProfile


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


def test_apply_constraints_adds_profile_routing():
    resolved = resolve_profile(device_id="dev-1")
    task = {
        "task_id": "t-1",
        "route_policy": {"route_role": "device_draw", "model_required": True},
    }

    result = apply_profile_constraints(task, resolved)

    assert "profile_routing" in result
    assert result["profile_routing"]["complete"] is False
    assert result["profile_routing"]["max_path_points"] == CONSERVATIVE_MAX_PATH_POINTS


def test_apply_constraints_downgrades_model_required_when_incomplete():
    resolved = resolve_profile(device_id="dev-1")
    task = {
        "task_id": "t-1",
        "route_policy": {"route_role": "device_draw", "model_required": True},
    }

    result = apply_profile_constraints(task, resolved)

    assert result["route_policy"]["approval_required"] is True
    assert result["route_policy"]["approval_reason"] == "incomplete device profile"


def test_apply_constraints_no_downgrade_when_complete():
    profile = DeviceProfile(
        profile_id="u8-full",
        model="U8",
        max_path_points=200,
    )
    register_profile(profile)
    resolved = resolve_profile(profile_id="u8-full", device_id="dev-1")
    task = {
        "task_id": "t-1",
        "route_policy": {"route_role": "device_draw", "model_required": True},
    }

    result = apply_profile_constraints(task, resolved)

    assert result["route_policy"].get("approval_required") is None
    assert result["profile_routing"]["complete"] is True


def test_apply_constraints_no_downgrade_for_control_tasks():
    resolved = resolve_profile(device_id="dev-1")
    task = {
        "task_id": "t-1",
        "route_policy": {"route_role": "device_control", "model_required": False},
    }

    result = apply_profile_constraints(task, resolved)

    assert result["route_policy"].get("approval_required") is None


def test_record_simplification():
    original = {"max_path_points": 200, "max_feed": 1200.0}
    constrained = {"max_path_points": 100, "max_feed": 1200.0}

    record_simplification(
        device_id="dev-1",
        task_id="t-1",
        simplification_type="cap_path_points",
        reason="device profile limit",
        original=original,
        constrained=constrained,
    )

    assert True  # If we reach here, the logging succeeded


def test_apply_profile_constraints_records_simplification():
    from device_gateway.profiles import apply_profile_constraints, resolve_profile

    resolved = resolve_profile(device_id="dev-1")
    task = {
        "task_id": "t-1",
        "device_id": "dev-1",
        "route_policy": {"route_role": "device_draw", "model_required": True},
    }

    result = apply_profile_constraints(task, resolved)

    assert result["route_policy"]["approval_required"] is True
    assert result["route_policy"]["approval_reason"] == "incomplete device profile"


def test_apply_profile_constraints_no_simplification_for_complete_profile():
    profile = DeviceProfile(
        profile_id="u8-full",
        model="U8",
        max_path_points=200,
    )
    register_profile(profile)
    resolved = resolve_profile(profile_id="u8-full", device_id="dev-1")
    task = {
        "task_id": "t-1",
        "device_id": "dev-1",
        "route_policy": {"route_role": "device_draw", "model_required": True},
    }

    result = apply_profile_constraints(task, resolved)

    assert result["route_policy"].get("approval_required") is None
