"""Device task projection helpers and store facade."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from device_artifacts.store import artifact_store
from device_intelligence.recovery import recovery_action
from device_intelligence.simulator import simulate_motion
from device_intelligence.schemas import TaskPlan
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_policy import policy_engine
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from .device_route_memory import get_route_memory, record_route_decision
from .intent import resolve_voice_task
from .model_routing import looks_like_svg_path, resolve_device_route_policy
from .profiles import apply_profile_constraints, resolve_profile
from .safety import DEFAULT_FEED, safe_point
from .path_validator import validate_capability_params, validate_route_policy
from .path_pipeline import render_svg_task, render_text_task
from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "get_device_info"})
TERMINAL_PHASES = frozenset({"done", "failed", "cancelled"})


def reset_tasks_for_tests() -> None:
    store_mod.task_store.reset()
    ledger_store.reset()
    artifact_store.reset()
    workflow.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


def _looks_like_svg_path(text: str) -> bool:
    """Heuristic: does the text look like an SVG path 'd' attribute?"""
    return looks_like_svg_path(text)


def project_to_motion_task(device_id: str, voice_task: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    capability = voice_task["capability"]
    params = voice_task.get("params", {})
    route_policy = resolve_device_route_policy(voice_task)

    # Validate route_policy against Edge-C schema before task creation
    validated_policy, policy_error = validate_route_policy(route_policy, capability)
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
        _record_route_evidence_artifact(task)
        return task

    # Resolve profile for routing decisions
    fw_rev = voice_task.get("fw_rev", "")
    resolved = resolve_profile(device_id=device_id, fw_rev=fw_rev)

    # Block dispatch when firmware is incompatible
    if resolved.routing_hints.get("block_dispatch"):
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
                "reason": resolved.routing_hints.get("block_reason", "firmware incompatible"),
            },
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="blocked")
        _record_task_created(task, status="blocked")
        _record_route_evidence_artifact(task)
        return task

    # Create task from voice intent
    task = _create_task_from_voice_task(device_id, voice_task, request_id, route_policy, params, capability)

    # Apply profile constraints to add routing metadata
    task = apply_profile_constraints(task, resolved)

    # Record route decision for sticky routing only when:
    # 1. Profile is complete (known device)
    # 2. Firmware is compatible
    # 3. No approval required (task not downgraded)
    approval_required = task.get("route_policy", {}).get("approval_required", False)
    if resolved.complete and resolved.fw_compatible and not approval_required:
        task_id = task.get("task_id", "")
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

    sanitized, error = validate_capability_params(capability, run_params)
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
        _record_route_evidence_artifact(task)
        return task

    task_id = _next_task_id()

    # M3: policy gate — evaluate before storing
    policy_result = policy_engine.decide(
        capability=capability,
        device_id=device_id,
        fw_rev=voice_task.get("fw_rev", ""),
        params=sanitized,
        profile=voice_task.get("profile"),
    )
    policy_dict = policy_result.to_dict()

    # Block dispatch when policy is not allow
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
        _record_route_evidence_artifact(task)
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

    # M4: workflow — register and advance through plan → sim
    workflow.register(task_id)
    workflow.advance(task_id, TaskState.PLANNED)

    # M4: simulator — compute motion metrics
    sim_plan = TaskPlan(
        plan_id=f"sim-{task_id}",
        device_id=device_id,
        capability=task["capability"],
        params=sanitized,
    )
    sim_result = simulate_motion(sim_plan)
    task["simulation"] = sim_result.to_dict()

    # Decide if approval is needed (high risk → waiting_approval)
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


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    summary = store_mod.task_store.record_motion_event(event)
    # M4: advance workflow on running/terminal events
    task_id = str(event.get("task_id", ""))
    phase = event.get("phase", "")
    payload: dict[str, Any] = {"motion_event": event}
    if phase == "failed":
        recovery = _recovery_for_event(event)
        if recovery is not None:
            payload["recovery"] = asdict(recovery)
    _advance_workflow_on_event(task_id, phase)
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=str(event.get("device_id", "")),
            payload=payload,
        )
    )
    if phase in TERMINAL_PHASES:
        ledger_store.append_event(
            new_event(
                event_type="task_terminal",
                task_id=task_id,
                device_id=str(event.get("device_id", "")),
                payload={"terminal_event": event},
            )
        )
        artifact_store.put_artifact(
            task_id=task_id,
            artifact_type="terminal_result",
            content=event,
            retention_days=90,
        )
    return summary


def _recovery_for_event(event: dict[str, Any]) -> Any | None:
    error = event.get("error")
    code = ""
    if isinstance(error, dict):
        code = str(error.get("code", ""))
    code = code or str(event.get("error_code", ""))
    if not code:
        return None
    return recovery_action(code)


def _advance_workflow_on_event(task_id: str, phase: str) -> None:
    """Best-effort workflow advancement from motion events."""
    if not task_id:
        return
    try:
        current = workflow.get_state(task_id)
    except Exception:
        return
    if phase == "processing" and current == TaskState.DISPATCHED:
        workflow.advance(task_id, TaskState.RUNNING)
    elif phase in TERMINAL_PHASES and current in (TaskState.RUNNING, TaskState.RECOVERING):
        workflow.advance(task_id, TaskState.TERMINAL)


def task_snapshot(task_id: str) -> dict[str, Any] | None:
    return store_mod.task_store.task_snapshot(task_id)


def active_tasks_for_device(device_id: str) -> list[dict[str, Any]]:
    return store_mod.task_store.active_tasks_for_device(device_id)


def enqueue_pending_task(device_id: str, task: dict[str, Any]) -> int:
    return store_mod.task_store.enqueue_pending_task(device_id, task)


def pop_pending_tasks(device_id: str, limit: int = 16) -> list[dict[str, Any]]:
    return store_mod.task_store.pop_pending_tasks(device_id, limit=limit)


def requeue_pending_tasks(device_id: str, tasks: list[dict[str, Any]]) -> int:
    return store_mod.task_store.requeue_pending_tasks(device_id, tasks)


def mark_task_dispatched(task_id: str) -> None:
    store_mod.task_store.mark_task_dispatched(task_id)
    # M4: advance workflow to dispatched
    try:
        current = workflow.get_state(task_id)
        if current == TaskState.READY_TO_DISPATCH:
            workflow.advance(task_id, TaskState.DISPATCHED)
    except Exception:
        pass  # best-effort for legacy tasks
    snapshot = store_mod.task_store.task_snapshot(task_id)
    task = snapshot.get("task") if snapshot else None
    device_id = str(task.get("device_id", "")) if isinstance(task, dict) else ""
    ledger_store.append_event(
        new_event(
            event_type="task_dispatched",
            task_id=task_id,
            device_id=device_id,
            payload={"task_id": task_id},
        )
    )


def ack_processing_task(device_id: str, task_id: str) -> bool:
    return store_mod.task_store.ack_processing(device_id, task_id)


def recover_stale_processing(device_id: str, timeout_sec: float = 120.0) -> int:
    return store_mod.task_store.recover_stale_processing(device_id, timeout_sec=timeout_sec)


def pending_count(device_id: str | None = None) -> int:
    return store_mod.task_store.pending_count(device_id)


def _record_task_created(task: dict[str, Any], status: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=str(task["task_id"]),
            device_id=str(task.get("device_id", "")),
            payload={"task": task, "status": status},
        )
    )


def _record_preview_artifact(task: dict[str, Any]) -> None:
    params = task.get("params", {})
    if not isinstance(params, dict):
        return
    preview_svg = params.get("preview_svg")
    if not isinstance(preview_svg, str) or not preview_svg:
        return
    artifact_store.put_artifact(
        task_id=str(task["task_id"]),
        artifact_type="preview_svg",
        content=preview_svg,
        retention_days=30,
    )


def _record_route_evidence_artifact(task: dict[str, Any]) -> None:
    """Store route decision evidence as a queryable artifact.

    Records route_role, primary_strategy, model_required, policy decision,
    validation results, and simulation summary so the full route-to-motion
    trace is auditable.
    """
    route_policy = task.get("route_policy")
    if not isinstance(route_policy, dict):
        return
    evidence: dict[str, Any] = {
        "route_role": route_policy.get("route_role", ""),
        "primary_strategy": route_policy.get("primary_strategy", ""),
        "model_required": route_policy.get("model_required", False),
        "artifact_required": route_policy.get("artifact_required", "none"),
        "capability": task.get("capability", ""),
        "source": task.get("source", ""),
    }
    policy = task.get("policy")
    if isinstance(policy, dict):
        evidence["policy_decision"] = policy.get("decision", "")
        evidence["policy_reason"] = policy.get("reason", "")
    simulation = task.get("simulation")
    if isinstance(simulation, dict):
        evidence["sim_risk_score"] = simulation.get("risk_score", 0.0)
        evidence["sim_runtime_sec"] = simulation.get("estimated_runtime_sec", 0.0)
    workflow_state = task.get("workflow_state")
    if workflow_state:
        evidence["workflow_state"] = workflow_state
    error = task.get("error")
    if isinstance(error, dict):
        evidence["error_code"] = error.get("code", "")
        evidence["error_reason"] = error.get("reason", "")
    # Record task status for validation trace
    task_status = task.get("status", "")
    if task_status:
        evidence["task_status"] = task_status
    artifact_store.put_artifact(
        task_id=str(task["task_id"]),
        artifact_type="route_evidence",
        content=evidence,
        retention_days=90,
    )
