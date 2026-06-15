"""Device task creation and motion_task projection."""

from __future__ import annotations

from typing import Any

from device_intelligence.schemas import TaskPlan
from device_intelligence.simulator import simulate_motion
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from .device_route_memory import record_route_decision
from .intent import resolve_voice_task
from .model_routing import CONTROL_CAPABILITIES, looks_like_svg_path
from .path_pipeline import render_svg_task, render_text_task
from .safety import DEFAULT_FEED, safe_point
from .task_recorder import (
    record_preview_artifact as _record_preview_artifact,
    record_route_evidence_artifact as _record_route_evidence_artifact,
    record_task_created as _record_task_created,
)
from . import store as store_mod
from . import task_deps as deps


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


def _looks_like_svg_path(text: str) -> bool:
    """Heuristic: does the text look like an SVG path 'd' attribute?"""
    return looks_like_svg_path(text)


def project_to_motion_task(device_id: str, voice_task: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    capability = voice_task["capability"]
    params = voice_task.get("params", {})
    fw_rev = str(voice_task.get("fw_rev", "") or "")
    profile_id = str(voice_task.get("profile_id", "") or "")
    shadow_profile = voice_task.get("shadow_profile") if isinstance(voice_task.get("shadow_profile"), dict) else None

    resolved = deps.resolve_profile(
        device_id=device_id,
        profile_id=profile_id,
        fw_rev=fw_rev,
        shadow_profile=shadow_profile,
    )
    route_policy = deps.resolve_device_route_policy(
        voice_task,
        device_id=device_id,
        profile_id=profile_id,
        fw_rev=fw_rev,
        shadow_profile=shadow_profile,
        resolved_profile=resolved,
    )

    validated_policy, policy_error = deps.validate_route_policy(route_policy, capability)
    if policy_error:
        task_id = _next_task_id()
        task = {
            "type": "motion_task",
            "task_id": task_id,
            "device_id": device_id,
            "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
            "source": voice_task.get("source", "voice"),
            "params": {},
            "route_policy": route_policy,
            "error": {"code": policy_error, "reason": f"route_policy validation failed: {policy_error}"},
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="failed")
        _record_task_created(task, status="failed")
        _record_route_evidence_artifact(task, scenario="route_policy_invalid")
        return task

    if resolved.routing_hints.get("block_dispatch") or route_policy.get("dispatch_blocked"):
        task_id = _next_task_id()
        task = {
            "type": "motion_task",
            "task_id": task_id,
            "device_id": device_id,
            "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
            "source": voice_task.get("source", "voice"),
            "params": {},
            "route_policy": route_policy,
            "profile_routing": {
                "profile_id": resolved.profile.profile_id,
                "complete": resolved.complete,
                "fw_compatible": resolved.fw_compatible,
                "max_path_points": resolved.profile.max_path_points,
                "max_feed": resolved.profile.max_feed,
            },
            "error": {
                "code": "fw_incompatible",
                "reason": resolved.routing_hints.get("block_reason")
                or route_policy.get("block_reason", "firmware incompatible"),
            },
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="blocked")
        _record_task_created(task, status="blocked")
        _record_route_evidence_artifact(task, scenario="dispatch_blocked")
        return task

    task = _create_task_from_voice_task(device_id, voice_task, request_id, route_policy, params, capability)
    task = deps.apply_profile_constraints(task, resolved)

    approval_required = task.get("route_policy", {}).get("approval_required", False)
    if resolved.complete and resolved.fw_compatible and not approval_required:
        backend = route_policy.get("backend", "unknown")
        record_route_decision(device_id, backend, True)

    return task


def _create_task_from_voice_task(
    device_id: str,
    voice_task: dict[str, Any],
    request_id: str | None,
    route_policy: dict[str, Any],
    params: dict[str, Any],
    capability: str,
) -> dict[str, Any]:
    """Create a task from a voice task intent."""
    if capability == "write_text":
        rendered = render_text_task(str(params.get("text", "")))
        run_params = {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
            "preview_svg": rendered.get("preview_svg", ""),
        }
    elif capability == "draw_generated":
        prompt = str(params.get("prompt", ""))[:120]
        if _looks_like_svg_path(prompt):
            rendered = render_svg_task(prompt)
        else:
            rendered = render_text_task(prompt or "?")
        run_params = {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "draw_generated",
            "prompt": prompt,
            "preview_svg": rendered.get("preview_svg", ""),
        }
    elif capability in CONTROL_CAPABILITIES:
        run_params = {
            "source_capability": capability,
        }
    else:
        run_params = {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}

    sanitized, error = deps.validate_capability_params(capability, run_params)
    if error:
        task_id = _next_task_id()
        task = {
            "type": "motion_task",
            "task_id": task_id,
            "device_id": device_id,
            "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
            "source": voice_task.get("source", "voice"),
            "params": {},
            "route_policy": route_policy,
            "error": {"code": error, "reason": f"validation failed: {error}"},
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="failed")
        _record_task_created(task, status="failed")
        _record_route_evidence_artifact(task, scenario="validation_failed")
        return task

    task_id = _next_task_id()

    policy_result = deps.policy_engine.decide(
        capability=capability,
        device_id=device_id,
        fw_rev=voice_task.get("fw_rev", ""),
        params=sanitized,
        profile=voice_task.get("profile"),
    )
    policy_dict = policy_result.to_dict()

    if policy_result.decision != "allow":
        task = {
            "type": "motion_task",
            "task_id": task_id,
            "device_id": device_id,
            "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
            "source": voice_task.get("source", "voice"),
            "params": {},
            "route_policy": route_policy,
            "policy": policy_dict,
            "error": {"code": f"policy_{policy_result.decision}", "reason": policy_result.reason},
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="blocked")
        _record_task_created(task, status="blocked")
        _record_route_evidence_artifact(task, scenario="policy_blocked")
        return task

    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
        "source": voice_task.get("source", "voice"),
        "params": sanitized,
        "route_policy": route_policy,
        "policy": policy_dict,
    }
    if request_id:
        task["request_id"] = request_id

    workflow.register(task_id)
    workflow.advance(task_id, TaskState.PLANNED)

    sim_plan = TaskPlan(
        plan_id=f"sim-{task_id}",
        device_id=device_id,
        capability=task["capability"],
        params=sanitized,
    )
    sim_result = simulate_motion(sim_plan)
    task["simulation"] = sim_result.to_dict()

    if sim_result.risk_score >= 0.7:
        workflow.advance(task_id, TaskState.SIMULATED)
        workflow.advance(task_id, TaskState.WAITING_APPROVAL)
        task["workflow_state"] = TaskState.WAITING_APPROVAL.value
    else:
        workflow.advance(task_id, TaskState.SIMULATED)
        workflow.advance(task_id, TaskState.READY_TO_DISPATCH)
        task["workflow_state"] = TaskState.READY_TO_DISPATCH.value

    store_mod.task_store.create_task_state(task, status="created")
    _record_task_created(task, status="created")
    _record_preview_artifact(task)
    _record_route_evidence_artifact(task)
    return task


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return project_to_motion_task(device_id, resolve_voice_task(text), request_id)
