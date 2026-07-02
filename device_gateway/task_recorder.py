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
_write_locks: dict[str, threading.Lock] = {}
_write_locks_lock = threading.Lock()
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
    request_id: str = "",
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
        "request_id": request_id,
        "_rseq": next(_record_seq),
    }
    _get_executor().submit(_write_evidence, device_id, evidence)


def record_route_evidence_sync(
    device_id: str,
    task_id: str,
    route_policy: dict[str, Any],
    selected_model: str = "",
    backend: str = "",
    reason: str = "",
    alternatives: list[dict[str, Any]] | None = None,
    request_id: str = "",
) -> None:
    """Synchronous route-evidence write for tests and flush-sensitive callers."""
    evidence = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "task_id": task_id,
        "route_policy": route_policy,
        "selected_model": selected_model,
        "backend": backend,
        "reason": reason,
        "alternatives": alternatives or [],
        "request_id": request_id,
        "_rseq": next(_record_seq),
    }
    _write_evidence(device_id, evidence)


def _get_write_lock(device_id: str) -> threading.Lock:
    """Return a per-device write lock, creating one on first use."""
    with _write_locks_lock:
        lock = _write_locks.get(device_id)
        if lock is None:
            lock = threading.Lock()
            _write_locks[device_id] = lock
        return lock


def _write_evidence(device_id: str, evidence: dict[str, Any]) -> None:
    """Write a single evidence record as JSON Lines to the device log file."""
    log_path = _STORAGE_BASE / f"route_evidence_{device_id}.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(evidence, ensure_ascii=False, default=str)
        with _get_write_lock(device_id):
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
    with _write_locks_lock:
        _write_locks.clear()


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


from device_gateway.route_evidence_builder import (  # noqa: E402,F401
    _build_route_evidence_content,
    _persist_route_evidence,
    record_route_evidence_artifact,
    record_device_consumed_route_evidence,
    record_recovery_route_evidence,
)
