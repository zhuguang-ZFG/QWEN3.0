"""Error and blocked-task builders for device task creation."""

from __future__ import annotations

from typing import Any

from .model_routing import CONTROL_CAPABILITIES
from .task_recorder import (
    record_route_evidence_artifact as _record_route_evidence_artifact,
    record_task_created as _record_task_created,
)
from . import store as store_mod


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


def _build_error_task(
    device_id: str,
    voice_task: dict,
    request_id: str | None,
    route_policy: dict,
    capability: str,
    error_code: str,
    error_reason: str,
    status: str,
    scenario: str,
) -> dict[str, Any]:
    """Build a failed/blocked motion task."""
    task_id = _next_task_id()
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
        "source": voice_task.get("source", "voice"),
        "params": {},
        "route_policy": route_policy,
        "error": {"code": error_code, "reason": error_reason},
    }
    if request_id:
        task["request_id"] = request_id
    store_mod.task_store.create_task_state(task, status=status)
    _record_task_created(task, status=status)
    _record_route_evidence_artifact(task, scenario=scenario)
    return task


def _null_guard_error_task(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    value: Any,
    error_code: str,
    reason: str,
    scenario: str,
) -> dict[str, Any] | None:
    """Return an error task when a required build step produced None."""
    if value is None:
        return _build_error_task(
            device_id,
            voice_task,
            request_id,
            route_policy,
            capability,
            error_code,
            reason,
            "failed",
            scenario,
        )
    return None


def _handle_policy_error(
    device_id: str,
    voice_task: dict,
    request_id: str | None,
    route_policy: dict,
    capability: str,
    policy_error: str,
) -> dict[str, Any]:
    """Build and record a policy-error task."""
    return _build_error_task(
        device_id,
        voice_task,
        request_id,
        route_policy,
        capability,
        policy_error,
        f"route_policy validation failed: {policy_error}",
        "failed",
        "route_policy_invalid",
    )


def _handle_dispatch_blocked(
    device_id: str,
    voice_task: dict,
    request_id: str | None,
    route_policy: dict,
    capability: str,
    resolved: Any,
) -> dict[str, Any]:
    """Build and record a dispatch-blocked task."""
    task = _build_error_task(
        device_id,
        voice_task,
        request_id,
        route_policy,
        capability,
        "fw_incompatible",
        resolved.routing_hints.get("block_reason") or route_policy.get("block_reason", "firmware incompatible"),
        "blocked",
        "dispatch_blocked",
    )
    task["profile_routing"] = {
        "profile_id": resolved.profile.profile_id,
        "complete": resolved.complete,
        "fw_compatible": resolved.fw_compatible,
        "max_path_points": resolved.profile.max_path_points,
        "max_feed": resolved.profile.max_feed,
    }
    return task
