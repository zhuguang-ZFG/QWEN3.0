"""Task recording helpers — ledger events and artifact storage."""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from device_artifacts.store import artifact_store
from device_ledger.events import new_event
from device_ledger.store import ledger_store

# Module-level executor for non-blocking route-evidence writes
_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()
_write_lock = threading.Lock()  # Serialize writes to avoid file-level races
_record_seq = iter(range(9, 1 << 32))  # Monotonic sequence for evidence uniqueness

# Storage base directory
_STORAGE_BASE = Path("device_artifacts")

_log = logging.getLogger(__name__)


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="artifact")
    return _executor


def record_route_evidence(
    device_id: str,
    task_id: str,
    route_policy: dict[str, Any],
    selected_model: str = "",
    backend: str = "",
    reason: str = "",
    alternatives: list[dict[str, Any]] | None = None,
) -> None:
    """Submit a route-evidence record for async JSON Lines write. Never blocks."""
    evidence = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "task_id": task_id,
        "route_policy": route_policy,
        "selected_model": selected_model,
        "backend": backend,
        "reason": reason,
        "alternatives": alternatives or [],
        "_rseq": next(_record_seq),
    }
    _get_executor().submit(_write_evidence, device_id, evidence)


def _write_evidence(device_id: str, evidence: dict[str, Any]) -> None:
    """Write a single evidence record as JSON Lines to the device log file."""
    log_path = _STORAGE_BASE / f"route_evidence_{device_id}.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(evidence, ensure_ascii=False, default=str)
        with _write_lock:
            with open(str(log_path), "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
    except OSError as e:
        _log.warning("Failed to write route evidence for device %s: %s", device_id, e)


def shutdown(wait: bool = True) -> None:
    """Gracefully shut down the executor, optionally waiting for pending writes."""
    global _executor, _record_seq
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=wait)
            _executor = None
        _record_seq = iter(range(9, 1 << 32))


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
    record_route_evidence(
        device_id=device_id,
        task_id=task_id,
        route_policy=route_policy,
        backend=str(content.get("backend", "")),
        reason=str(content.get("scenario", "")),
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
