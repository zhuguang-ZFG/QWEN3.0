"""路由证据内容构建与持久化 — 从 task_recorder.py 拆出以控制行数。

依赖 ``record_route_evidence``（仍在 task_recorder）通过延迟 import 访问，
避免循环导入并保持对外接口不变。
"""

from __future__ import annotations

from typing import Any

from device_artifacts.store import artifact_store


def _build_route_evidence_content(task: dict[str, Any], scenario: str) -> dict[str, Any] | None:
    route_policy = task.get("route_policy")
    if not isinstance(route_policy, dict):
        return None
    evidence: dict[str, Any] = {
        "scenario": scenario,
        "route_role": route_policy.get("route_role", ""),
        "primary_strategy": route_policy.get("primary_strategy", ""),
        "model_required": route_policy.get("model_required", False),
        "artifact_required": route_policy.get("artifact_required", "none"),
        "backend": route_policy.get("backend", ""),
        "capability": task.get("capability", ""),
        "source": task.get("source", ""),
        "request_id": task.get("request_id", ""),
        "entrypoint": task.get("entrypoint", task.get("source", "")),
    }
    device_capabilities = task.get("device_capabilities")
    if isinstance(device_capabilities, list) and device_capabilities:
        evidence["device_capabilities"] = list(device_capabilities)
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
    return evidence


def _persist_route_evidence(
    *,
    task_id: str,
    device_id: str,
    route_policy: dict[str, Any],
    content: dict[str, Any],
) -> None:
    artifact_store.put_artifact(
        task_id=task_id,
        artifact_type="route_evidence",
        content=content,
        retention_days=90,
    )
    import device_gateway.task_recorder as _t  # 延迟导入避免循环

    _t.record_route_evidence(
        device_id=device_id,
        task_id=task_id,
        route_policy=route_policy,
        backend=str(content.get("backend", "")),
        reason=str(content.get("scenario", "")),
        request_id=str(content.get("request_id", "")),
    )


def record_route_evidence_artifact(task: dict[str, Any], *, scenario: str = "task_created") -> None:
    """Store route decision evidence as a queryable artifact and JSONL log entry."""
    content = _build_route_evidence_content(task, scenario)
    if content is None:
        return
    route_policy = task.get("route_policy")
    assert isinstance(route_policy, dict)
    _persist_route_evidence(
        task_id=str(task["task_id"]),
        device_id=str(task.get("device_id", "")),
        route_policy=route_policy,
        content=content,
    )


def record_device_consumed_route_evidence(task_id: str, event: dict[str, Any]) -> None:
    """Persist device-reported route_policy_evidence from a terminal motion_event."""
    device_evidence = event.get("route_policy_evidence")
    if not isinstance(device_evidence, dict):
        return
    content: dict[str, Any] = {
        "scenario": "device_consumed",
        "phase": event.get("phase", ""),
        "request_id": event.get("request_id", ""),
        **device_evidence,
    }
    route_policy = {
        "route_role": device_evidence.get("route_role", ""),
        "model_required": device_evidence.get("model_required", False),
        "primary_strategy": device_evidence.get("primary_strategy", ""),
        "artifact_required": device_evidence.get("artifact_required", "none"),
        "backend": device_evidence.get("backend", ""),
    }
    _persist_route_evidence(
        task_id=task_id,
        device_id=str(event.get("device_id", "")),
        route_policy=route_policy,
        content=content,
    )


def record_recovery_route_evidence(
    task_id: str,
    device_id: str,
    recovery_result: dict[str, Any],
    task: dict[str, Any] | None = None,
) -> None:
    """Record recovery action against the task's route context."""
    route_policy = {}
    capability = ""
    if isinstance(task, dict):
        capability = str(task.get("capability", ""))
        policy = task.get("route_policy")
        if isinstance(policy, dict):
            route_policy = policy
    content: dict[str, Any] = {
        "scenario": "recovery",
        "recovery_action": recovery_result.get("action", ""),
        "recovery_attempt": recovery_result.get("attempt", 0),
        "route_role": route_policy.get("route_role", ""),
        "backend": route_policy.get("backend", ""),
        "capability": capability,
        "request_id": task.get("request_id", "") if isinstance(task, dict) else "",
    }
    if not route_policy:
        _persist_route_evidence(
            task_id=task_id,
            device_id=device_id,
            route_policy={
                "route_role": "",
                "model_required": False,
                "primary_strategy": "",
                "artifact_required": "none",
            },
            content=content,
        )
        return
    _persist_route_evidence(
        task_id=task_id,
        device_id=device_id,
        route_policy=route_policy,
        content=content,
    )
