"""Device task creation helper builders."""

from __future__ import annotations

import asyncio
from typing import Any

from device_intelligence.schemas import TaskPlan
from device_intelligence.simulator import simulate_motion
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from .model_routing import CONTROL_CAPABILITIES
from .path_pipeline import PathNormalizationError, _normalize_path_to_workspace
from .path_validator import _MOVE_CAPABILITIES, _PATH_GENERATING_CAPABILITIES
from .safety import DEFAULT_WORKSPACE_MM
from .task_creation_errors import (
    _build_error_task,
    _handle_dispatch_blocked,
    _handle_policy_error,
    _next_task_id,
    _null_guard_error_task,
)
from .task_draw_params import build_run_params_async
from .task_recorder import (
    record_preview_artifact as _record_preview_artifact,
    record_route_evidence_artifact as _record_route_evidence_artifact,
)
from . import store as store_mod
from . import task_creation as deps

__all__ = [
    "_resolve_route_context",
    "_handle_policy_error",
    "_handle_dispatch_blocked",
    "_build_error_task",
    "_run_task_simulation",
    "_build_run_params_or_error",
    "_validate_params_or_error",
    "_apply_route_policy_or_blocked",
    "_assemble_motion_task",
    "_create_task_from_voice_task",
    "_next_task_id",
]


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


def _run_task_simulation(task: dict[str, Any], sanitized: dict, device_id: str) -> dict[str, Any]:
    """Register, simulate, and dispatch a task."""
    workflow.register(task["task_id"], device_id=device_id, task=task)
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


def _normalize_generated_path(
    run_params: dict[str, Any], capability: str, profile: Any
) -> tuple[dict[str, Any], str | None]:
    """GW-B1: fit server-generated paths inside the resolved profile workspace.

    write_text/draw_generated/handwriting paths previously skipped workspace
    normalization entirely; long text reached 183mm and was dispatched to
    60-100mm machines. Returns (params, error). Normalization failure is a
    hard reject, never a silent clamp.
    """
    if capability not in _PATH_GENERATING_CAPABILITIES:
        return run_params, None
    path = run_params.get("path")
    if not isinstance(path, list) or not path:
        return run_params, None
    workspace = profile.workspace_mm if profile is not None else DEFAULT_WORKSPACE_MM
    try:
        normalized = _normalize_path_to_workspace(path, width=float(workspace["x"]), height=float(workspace["y"]))
    except PathNormalizationError as exc:
        return run_params, str(exc)
    out = dict(run_params)
    out["path"] = normalized
    return out, None


def _clamp_params_to_profile(run_params: dict[str, Any], profile: Any) -> dict[str, Any]:
    """Clamp feed / path length to profile limits before validation.

    Feed and point-count overruns are clamped (matching the downstream
    apply_profile_constraints semantics); only workspace violations should
    hard-reject in profile_limit_error.
    """
    if profile is None:
        return run_params
    clamped = dict(run_params)
    feed = clamped.get("feed")
    if isinstance(feed, (int, float)) and feed > profile.max_feed:
        clamped["feed"] = profile.max_feed
    path = clamped.get("path")
    if isinstance(path, list) and len(path) > profile.max_path_points:
        clamped["path"] = path[: profile.max_path_points]
    return clamped


async def _validate_params_or_error(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    capability: str,
    run_params: dict[str, Any],
    profile: Any = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate sanitized params or return an error task."""
    run_params = _clamp_params_to_profile(run_params, profile)
    sanitized, error = deps.validate_capability_params(capability, run_params, profile=profile)
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
    # GW-R3-12: move_abs/move_rel dispatch to firmware under their own capability
    # name (cap_norm == "move_abs"/"move_rel"); they carry scalar coordinates, not
    # a path, so they must NOT be rewritten to run_path like drawing intents are.
    passthrough = capability in CONTROL_CAPABILITIES or capability in _MOVE_CAPABILITIES
    task = {
        "type": "motion_task",
        "task_id": _next_task_id(),
        "device_id": device_id,
        "capability": capability if passthrough else "run_path",
        "source": voice_task.get("source", "voice"),
        "entrypoint": voice_task.get("entrypoint", voice_task.get("source", "voice")),
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
    profile: Any = None,
) -> dict[str, Any]:
    """Create a task from a voice task intent."""
    ctx = (device_id, voice_task, request_id, route_policy, capability)

    run_params, error_task = await _build_run_params_or_error(*ctx, params)
    if error_task:
        return error_task
    if guard := _null_guard_error_task(*ctx, run_params, "task_build_failed", "task build failed", "task_build_failed"):
        return guard

    run_params, norm_error = _normalize_generated_path(run_params, capability, profile)
    if norm_error:
        return _build_error_task(
            *ctx, "E_BAD_PARAMS", f"path normalization failed: {norm_error}", "failed", "validation_failed"
        )

    sanitized, error_task = await _validate_params_or_error(*ctx, run_params, profile=profile)
    if error_task:
        return error_task
    if guard := _null_guard_error_task(
        *ctx, sanitized, "task_validation_failed", "task validation failed", "task_validation_failed"
    ):
        return guard

    policy_dict, error_task = _apply_route_policy_or_blocked(*ctx, sanitized)
    if error_task:
        return error_task
    if guard := _null_guard_error_task(
        *ctx, policy_dict, "task_policy_failed", "task policy failed", "task_policy_failed"
    ):
        return guard

    # GW-WD: simulation + task-store writes are synchronous (Redis/SQLite);
    # keep them off the event loop.
    return await asyncio.to_thread(_assemble_motion_task, *ctx, sanitized, policy_dict)
