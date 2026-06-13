"""Compat intent → device_gateway task bridge."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.responses import JSONResponse

from device_gateway.path_validator import validate_capability_params
from device_intelligence.schemas import TaskPlan
from device_intelligence.simulator import simulate_motion
from device_policy import policy_engine
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from .http_helpers import err


def gateway_capability(intent: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    if intent == "run_path":
        return "run_path", {**params, "source_capability": "run_path"}, None
    if intent == "draw_image":
        if not isinstance(params.get("path"), list):
            return "", {}, "draw_image requires params.path until imageUrl projection is wired"
        mapped = {**params, "source_capability": "draw_image"}
        if "imageUrl" in params:
            mapped["image_url"] = params["imageUrl"]
        return "run_path", mapped, None
    if intent == "home":
        return "home", {"source_capability": "home"}, None
    if intent == "calibrate":
        return "home", {"source_capability": "calibrate"}, None
    return "", {}, f"unsupported capability: {intent}"


def build_gateway_task(
    device_id: str,
    intent: str,
    params: dict[str, Any],
    source: str,
    request_id: str,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    capability, gateway_params, error = gateway_capability(intent, params)
    if error:
        return None, err(4001, error, 400)
    sanitized, validation_error = validate_capability_params(capability, gateway_params)
    if validation_error:
        return None, err(4002, f"validation failed: {validation_error}", 400)
    policy = policy_engine.decide(capability=capability, device_id=device_id, fw_rev="", params=sanitized)
    if policy.decision != "allow":
        return None, err(4003, policy.reason, 400)
    task_id = f"task-{uuid4().hex[:12]}"
    workflow.register(task_id)
    workflow.advance(task_id, TaskState.PLANNED)
    sim = simulate_motion(
        TaskPlan(plan_id=f"sim-{task_id}", device_id=device_id, capability=capability, params=sanitized),
    )
    workflow.advance(task_id, TaskState.SIMULATED)
    needs_approval = bool(source == "voice" and params.get("requireApproval")) or sim.risk_score >= 0.7
    workflow.advance(task_id, TaskState.WAITING_APPROVAL if needs_approval else TaskState.READY_TO_DISPATCH)
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "source": source,
        "params": sanitized,
        "policy": policy.to_dict(),
        "simulation": sim.to_dict(),
        "workflow_state": TaskState.WAITING_APPROVAL.value if needs_approval else TaskState.READY_TO_DISPATCH.value,
        "compat": {"intent": intent},
    }
    if request_id:
        task["request_id"] = request_id
    from device_gateway import store as store_mod

    store_mod.task_store.create_task_state(task, status="created")
    return task, None


async def dispatch_or_enqueue(device_id: str, task: dict[str, Any]) -> dict[str, Any]:
    from device_gateway.sessions import registry
    from device_gateway.tasks import enqueue_pending_task
    from routes.device_gateway_dispatch import dispatch_task_to_session, publish_task_available_safe

    session = registry.get(device_id)
    sent = False
    if session is not None:
        sent = await dispatch_task_to_session(session, task)
    queue_depth = 0
    if not sent:
        queue_depth = enqueue_pending_task(device_id, task)
        await publish_task_available_safe(device_id, str(task.get("task_id", "")))
    return {"sent": sent, "queueDepth": queue_depth, "dispatchStatus": "sent" if sent else "queued"}
