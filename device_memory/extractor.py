"""Task episode extraction from terminal ledger events."""

from __future__ import annotations

import time
from typing import Any

from device_ledger.events import LedgerEvent
from device_memory.schemas import MemoryEntry, MemoryType


def extract_episode_from_terminal(
    event: LedgerEvent,
    device_id: str,
    task_id: str,
) -> MemoryEntry | None:
    """Extract a structured task episode from a terminal ledger event.

    Only processes 'task_terminal' and 'motion_event' events when the phase
    is terminal (done/failed/cancelled). Returns None for non-terminal events
    or events with insufficient data.
    """
    payload = event.payload or {}
    terminal = payload.get("terminal_event") or payload.get("motion_event") or {}
    if not isinstance(terminal, dict):
        return None

    phase = terminal.get("phase", "")
    if phase not in ("done", "failed", "cancelled"):
        return None

    capability = terminal.get("capability", terminal.get("source_capability", "unknown"))
    task_type = _classify_task_type(capability, terminal)
    params = terminal.get("params", {})

    value_data: dict[str, Any] = {
        "phase": phase,
        "task_type": task_type,
        "capability": capability,
        "error": terminal.get("error"),
        "params_summary": _summarize_params(params),
    }

    if phase == "done":
        value_data["outcome"] = "success"
    elif phase == "failed":
        value_data["outcome"] = "failure"
    else:
        value_data["outcome"] = "cancelled"

    return MemoryEntry(
        id=f"ep-{task_id}-{event.event_id}",
        device_id=device_id,
        type=MemoryType.TASK_EPISODE,
        key=f"episode_{task_id}_{event.event_id}",
        value=_safe_json_dumps(value_data),
        ttl_days=60,
        created_at=int(time.time()),
        source="device_task",
        confidence=1.0 if phase == "done" else 0.3,
    )


def extract_device_failure_from_event(
    event: LedgerEvent,
    device_id: str,
) -> MemoryEntry | None:
    """Detect recurring failure patterns from motion events."""
    payload = event.payload or {}
    me = payload.get("motion_event") or {}
    if not isinstance(me, dict):
        return None

    if me.get("phase") != "failed":
        return None

    error = me.get("error") or {}
    code = error.get("code", "") if isinstance(error, dict) else str(error)
    if not code:
        return None

    return MemoryEntry(
        id=f"df-{event.event_id}",
        device_id=device_id,
        type=MemoryType.DEVICE_FAILURE,
        key=f"failure_{code}",
        value=_safe_json_dumps(
            {
                "error_code": code,
                "reason": error.get("reason", "") if isinstance(error, dict) else "",
                "capability": me.get("capability", ""),
                "timestamp": event.created_at,
            }
        ),
        ttl_days=14,
        created_at=int(time.time()),
        source="device_failure_event",
        confidence=0.8,
    )


def _classify_task_type(capability: str, _terminal: dict[str, Any]) -> str:
    if capability in ("write_text", "draw_generated"):
        return "creative"
    if capability in ("home", "estop", "pause", "resume"):
        return "control"
    if capability == "run_path":
        return "path_render"
    return "other"


def _summarize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Strip large fields (paths, base64 previews) from params for memory."""
    summary = {}
    for k, v in params.items():
        if k in ("path", "preview_svg", "preview_base64"):
            has = "present" if v else "empty"
            summary[k] = f"<{has}>"
        elif isinstance(v, (str, int, float, bool)):
            summary[k] = v
        else:
            summary[k] = str(type(v).__name__)
    return summary


def _safe_json_dumps(obj: Any) -> str:
    import json

    def _default(o: Any) -> str:
        return str(o)

    return json.dumps(obj, default=_default, ensure_ascii=False)
