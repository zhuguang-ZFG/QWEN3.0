"""Profile-aware route policy matrix tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.device_route_memory import reset_route_memory_for_tests
from device_gateway.profiles import register_profile, reset_profiles_for_tests
from device_intelligence.schemas import DeviceProfile


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


@pytest.fixture(autouse=True)
def _mock_device_draw(monkeypatch):
    monkeypatch.setattr(
        "device_gateway.task_draw_params.handle_device_draw",
        AsyncMock(
            return_value={
                "status": "success",
                "image_url": "",
                "svg_path": "M 10 10 L 50 50 L 90 10 Z",
                "width": 180,
                "height": 180,
                "model": "test-draw",
                "error": None,
            }
        ),
    )


def test_resolve_route_policy_incomplete_profile_gates_draw():
    from device_gateway.model_routing import resolve_device_route_policy

    policy = resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "画猫"}},
        device_id="dev-new",
    )

    assert policy["route_role"] == "device_draw"
    assert policy["profile_complete"] is False
    assert policy["approval_required"] is True
    assert policy["prefer_preset"] is True
    assert policy["downgrade_generated"] is True


def test_resolve_route_policy_complete_profile_no_draw_approval():
    from device_gateway.model_routing import resolve_device_route_policy

    profile = DeviceProfile(
        profile_id="u8-full",
        model="U8",
        max_path_points=200,
        capabilities=("home", "pause", "resume", "run_path", "stop", "write_text", "draw_generated"),
    )
    register_profile(profile)

    policy = resolve_device_route_policy(
        {"capability": "draw_generated", "params": {"prompt": "画猫"}},
        device_id="dev-1",
        profile_id="u8-full",
    )

    assert policy["profile_complete"] is True
    assert policy.get("approval_required") is None


def test_resolve_route_policy_fw_incompatible_sets_dispatch_blocked():
    from device_gateway.model_routing import resolve_device_route_policy

    profile = DeviceProfile(
        profile_id="u8-v2",
        model="U8",
        supported_fw_prefixes=("v2.",),
    )
    register_profile(profile)

    policy = resolve_device_route_policy(
        {"capability": "home", "params": {}},
        device_id="dev-1",
        profile_id="u8-v2",
        fw_rev="v1.0.0",
    )

    assert policy["dispatch_blocked"] is True
    assert policy["fw_compatible"] is False


def test_create_task_draw_unknown_device_requires_approval():
    from device_gateway.tasks import create_task_from_transcript

    task = create_task_from_transcript("dev-unknown", "draw cat")

    assert task["route_policy"]["approval_required"] is True
    assert task["route_policy"]["profile_complete"] is False
