"""Device task creation helper builders."""

from __future__ import annotations

from typing import Any

from device_intelligence.schemas import TaskPlan
from device_intelligence.simulator import simulate_motion
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from .model_routing import CONTROL_CAPABILITIES
from .task_draw_params import build_run_params_async
from .task_recorder import (
    record_preview_artifact as _record_preview_artifact,
    record_route_evidence_artifact as _record_route_evidence_artifact,
    record_task_created as _record_task_created,
)
from . import store as store_mod
from . import task_deps as deps


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


def _resolve_route_context(
    device_id: str,
    voice_task: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Resolve profile and route policy for a voice task."""
    fw_rev = str(voice_task.get("fw_rev", "") or "")
    profile_id = str(voice_task.get("profile_id", "") or "")
    shadow = voice_task.get("shadow_profile") if isinstance(voice_task.get("shadow_profile"), dict) else None
    resolved = deps.resolve_profile(device_id=device_id, profile_id=profile_id, fw_rev=fw_rev, shadow_profile=shadow)
    route_policy = deps.resolve_device_route_policy(
        voice_task,
        device_id=device_id,
        profile_id=profile_id,
        fw_rev=fw_rev,
        shadow_profile=shadow,
        resolved_profile=resolved,
    )
    return resolved, route_policy


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


def _run_task_simulation(task: dict[str, Any], sanitized: dict, device_id: str) -> dict[str, Any]:
    """Register, simulate, and dispatch a task."""
    workflow.register(task["task_id"])
    workflow.advance(task["task_id"], TaskState.PLANNED)
    sim_plan = TaskPlan(
        plan_id=f"sim-{task['task_id']}",
        device_id=device_id,
        capability=task["capability"],
        params=sanitized,
    )
    sim_result = simulate_motion(sim_plan)
    task["simulation"] = sim_result.to_dict()
    if sim_result.risk_score >= 0.7:
        workflow.advance(task["task_id"], TaskState.SIMULATED)
        workflow.advance(task["task_id"], TaskState.WAITING_APPROVAL)
        task["workflow_state"] = TaskState.WAITING_APPROVAL.value
    else:
        workflow.advance(task["task_id"], TaskState.SIMULATED)
        workflow.advance(task["task_id"], TaskState.READY_TO_DISPATCH)
        task["workflow_state"] = TaskState.READY_TO_DISPATCH.value
    store_mod.task_store.create_task_state(task, status="created")
    _record_task_created(task, status="created")
    _record_preview_artifact(task)
    _record_route_evidence_artifact(task)
    return task


async def _build_run_params_or_error(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Build run params or return an error task."""
    run_params, build_error = await build_run_params_async(capability, params, device_id)
    if build_error:
        return None, _build_error_task(
            device_id,
            voice_task,
            request_id,
            route_policy,
            capability,
            "draw_failed",
            build_error,
            "failed",
            "draw_generation_failed",
        )
    return run_params, None


async def _validate_params_or_error(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    run_params: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate sanitized params or return an error task."""
    sanitized, error = deps.validate_capability_params(capability, run_params)
    if error:
        return None, _build_error_task(
            device_id,
            voice_task,
            request_id,
            route_policy,
            capability,
            error,
            f"validation failed: {error}",
            "failed",
            "validation_failed",
        )
    return sanitized, None


def _apply_route_policy_or_blocked(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    sanitized: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Apply route policy and return policy dict or a blocked task."""
    policy_result = deps.policy_engine.decide(
        capability=capability,
        device_id=device_id,
        fw_rev=voice_task.get("fw_rev", ""),
        params=sanitized,
        profile=voice_task.get("profile"),
    )
    policy_dict = policy_result.to_dict()
    if policy_result.decision != "allow":
        task = _build_error_task(
            device_id,
            voice_task,
            request_id,
            route_policy,
            capability,
            f"policy_{policy_result.decision}",
            policy_result.reason,
            "blocked",
            "policy_blocked",
        )
        task["policy"] = policy_dict
        return None, task
    return policy_dict, None


def _assemble_motion_task(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    sanitized: dict[str, Any],
    policy_dict: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the final motion task and run simulation."""
    task = {
        "type": "motion_task",
        "task_id": _next_task_id(),
        "device_id": device_id,
        "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
        "source": voice_task.get("source", "voice"),
        "params": sanitized,
        "route_policy": route_policy,
        "policy": policy_dict,
    }
    if request_id:
        task["request_id"] = request_id
    return _run_task_simulation(task, sanitized, device_id)


async def _create_task_from_voice_task(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    params: dict[str, Any],
    capability: str,
) -> dict[str, Any]:
    """Create a task from a voice task intent."""
    run_params, error_task = await _build_run_params_or_error(
        device_id, voice_task, request_id, route_policy, capability, params
    )
    if error_task:
        return error_task

    sanitized, error_task = await _validate_params_or_error(
        device_id, voice_task, request_id, route_policy, capability, run_params
    )
    if error_task:
        return error_task

    policy_dict, error_task = _apply_route_policy_or_blocked(
        device_id, voice_task, request_id, route_policy, capability, sanitized
    )
    if error_task:
        return error_task

    return _assemble_motion_task(device_id, voice_task, request_id, route_policy, capability, sanitized, policy_dict)
