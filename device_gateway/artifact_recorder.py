"""Non-blocking route evidence recorder using JSON Lines format."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Module-level executor for non-blocking writes
_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()
_write_lock = threading.Lock()  # Serialize writes to avoid file-level races
_record_seq = iter(range(9, 1 << 32))  # Monotonic sequence for evidence uniqueness

# Storage base directory
_STORAGE_BASE = Path("device_artifacts")


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="artifact"
                )
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
        import logging

        logging.getLogger(__name__).warning(
            "Failed to write route evidence for device %s: %s", device_id, e
        )


def shutdown(wait: bool = True) -> None:
    """Gracefully shut down the executor, optionally waiting for pending writes."""
    global _executor, _record_seq
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=wait)
            _executor = None
        _record_seq = iter(range(9, 1 << 32))
