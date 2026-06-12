"""Task recording helpers — ledger events and artifact storage."""

from __future__ import annotations

from typing import Any

from device_artifacts.store import artifact_store
from device_ledger.events import new_event
from device_ledger.store import ledger_store


def record_task_created(task: dict[str, Any], status: str) -> None:
    """Record a task creation event in the ledger."""
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=str(task["task_id"]),
            device_id=str(task.get("device_id", "")),
            payload={"task": task, "status": status},
        )
    )


def record_preview_artifact(task: dict[str, Any]) -> None:
    """Store preview SVG artifact for operator replay."""
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


def record_route_evidence_artifact(task: dict[str, Any]) -> None:
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
    task_status = task.get("status", "")
    if task_status:
        evidence["task_status"] = task_status
    artifact_store.put_artifact(
        task_id=str(task["task_id"]),
        artifact_type="route_evidence",
        content=evidence,
        retention_days=90,
    )
