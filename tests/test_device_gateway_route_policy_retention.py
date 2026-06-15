"""Ensure route_policy is preserved on all motion_task paths.

Stage 1 of the device routing roadmap requires every task — including
blocked, failed, and validation-rejected tasks — to carry its routing
policy so operators can explain why a route was chosen and why execution
stopped.
"""

from __future__ import annotations

from typing import Any

from device_gateway.tasks import project_to_motion_task, reset_tasks_for_tests
from device_policy.decisions import PolicyResult


def setup_function() -> None:
    reset_tasks_for_tests()


def _base_voice_task(capability: str = "draw_generated", params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "capability": capability,
        "params": params or {"prompt": "draw a circle"},
        "source": "voice",
    }


def test_route_policy_retained_on_route_policy_validation_failure(monkeypatch: Any) -> None:
    import device_gateway.task_deps as task_deps

    original = task_deps.validate_route_policy

    def fail_validation(route_policy: dict[str, Any], capability: str = "") -> tuple[dict[str, Any], str]:
        return route_policy, "invalid_policy"

    monkeypatch.setattr(task_deps, "validate_route_policy", fail_validation)
    try:
        task = project_to_motion_task("dev-1", _base_voice_task("home", {}))
    finally:
        monkeypatch.setattr(task_deps, "validate_route_policy", original)

    assert "route_policy" in task
    assert task["route_policy"]["route_role"] == "device_control"
    assert "error" in task


def test_route_policy_retained_on_firmware_incompatible(monkeypatch: Any) -> None:
    import device_gateway.task_deps as task_deps

    def blocked_profile(*, device_id: str = "", fw_rev: str = "", **kwargs: Any) -> Any:
        from device_gateway.profiles import ResolvedProfile, DeviceProfile

        return ResolvedProfile(
            profile=DeviceProfile(profile_id="test", device_id=device_id, max_path_points=100, max_feed=1000.0),
            complete=True,
            fw_compatible=False,
            routing_hints={"block_dispatch": True, "block_reason": "test fw blocked"},
        )

    monkeypatch.setattr(task_deps, "resolve_profile", blocked_profile)
    task = project_to_motion_task("dev-1", _base_voice_task())

    assert "route_policy" in task
    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["error"]["code"] == "fw_incompatible"


def test_route_policy_retained_on_capability_params_validation_failure(monkeypatch: Any) -> None:
    import device_gateway.task_deps as task_deps

    def bad_params(capability: str, params: dict[str, Any], profile: Any = None) -> tuple[dict[str, Any], str]:
        return {}, "bad_params"

    monkeypatch.setattr(task_deps, "validate_capability_params", bad_params)
    task = project_to_motion_task("dev-1", _base_voice_task())

    assert "route_policy" in task
    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["error"]["code"] == "bad_params"


def test_route_policy_retained_on_policy_rejection(monkeypatch: Any) -> None:
    import device_gateway.task_deps as task_deps

    monkeypatch.setattr(
        task_deps.policy_engine,
        "decide",
        lambda **kwargs: PolicyResult(decision="reject", reason="test rejection"),
    )
    task = project_to_motion_task("dev-1", _base_voice_task())

    assert "route_policy" in task
    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["policy"]["decision"] == "reject"


def test_route_policy_retained_on_policy_require_approval(monkeypatch: Any) -> None:
    import device_gateway.task_deps as task_deps

    monkeypatch.setattr(
        task_deps.policy_engine,
        "decide",
        lambda **kwargs: PolicyResult(decision="require_approval", reason="test approval gate"),
    )
    task = project_to_motion_task("dev-1", _base_voice_task())

    assert "route_policy" in task
    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["policy"]["decision"] == "require_approval"
