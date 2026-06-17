"""Device support snapshot: shadow, firmware, self-check, recent events."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from device_intelligence.shadow import shadow_store
from device_gateway import tasks as tasks_mod
from device_ledger.store import ledger_store
from device_memory.recall import get_device_failure_warnings
from routes.device_memory import get_memory_store

_log = logging.getLogger(__name__)


def build_support_snapshot(device_id: str) -> dict[str, Any]:
    """Build a operator-visible support snapshot for a device.

    Contains:
    - Shadow state (latest heartbeat, info, self_check)
    - Active task count
    - Recent failure warnings from memory
    - Recommendation (redacted, no raw child media)
    """
    shadow = shadow_store.snapshot(device_id) or {}
    recent_tasks = _list_recent_terminal_tasks(device_id, limit=10)

    failure_warnings = get_device_failure_warnings(get_memory_store(), device_id)

    # Count active tasks
    active = tasks_mod.active_tasks_for_device(device_id)

    # Build recommendation based on recent patterns
    recommendation = _build_recommendation(failure_warnings, recent_tasks)

    return {
        "device_id": device_id,
        "shadow": {
            "last_heartbeat_ms": shadow.get("last_heartbeat_ms"),
            "firmware_rev": shadow.get("firmware_rev", ""),
            "device_info": _redact_sensitive(shadow.get("device_info", {})),
            "last_self_check": _summarize_self_check(shadow.get("last_self_check")),
        },
        "active_tasks": len(active),
        "recent_terminal_tasks": len(recent_tasks),
        "failure_warnings": failure_warnings,
        "recommendation": recommendation,
    }


_RECENT_WINDOW_SECONDS = 24 * 3600  # Recommendations look at the last 24 hours


def _parse_event_timestamp(event: Any) -> float:
    """Best-effort parse of a ledger event's created_at timestamp."""
    raw = getattr(event, "created_at", "")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f+00:00"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return time.time()  # fallback: treat as current time


def _list_recent_terminal_tasks(
    device_id: str,
    limit: int = 10,
    window_seconds: float = _RECENT_WINDOW_SECONDS,
) -> list[dict[str, Any]]:
    """List recent terminal task events from the ledger. Best-effort."""
    try:
        events = ledger_store.events_for_device(device_id)
    except AttributeError:
        return []
    cutoff = time.time() - window_seconds
    terminal_events: list[dict[str, Any]] = []
    for ev in reversed(events):
        if ev.event_type == "task_terminal" and _parse_event_timestamp(ev) >= cutoff:
            payload = ev.payload or {}
            te = payload.get("terminal_event") or {}
            if isinstance(te, dict):
                terminal_events.append(
                    {
                        "task_id": ev.task_id,
                        "phase": te.get("phase", ""),
                        "capability": te.get("capability", te.get("source_capability", "")),
                        "created_at": ev.created_at,
                    }
                )
        if len(terminal_events) >= limit:
            break
    return terminal_events


def _build_recommendation(
    failure_warnings: list[dict[str, Any]],
    recent_tasks: list[dict[str, Any]],
) -> str:
    """Build redacted operator recommendation from recent patterns."""
    if not failure_warnings and not recent_tasks:
        return "设备运行正常，无需干预。"

    high_count = sum(1 for w in failure_warnings if w.get("error_code") in ("E_ESTOP", "E_NOT_HOMED"))
    if high_count > 0:
        return "设备存在急停或未回零记录，建议检查硬件状态后再下发任务。"

    limit_count = sum(1 for w in failure_warnings if "LIMIT" in str(w.get("error_code", "")))
    if limit_count >= 2:
        return "设备频繁触发限位，建议检查机械行程并重新校准归零点。"

    recent_failures = sum(1 for t in recent_tasks if t.get("phase") == "failed")
    if recent_failures >= 3:
        return f"最近 {len(recent_tasks)} 个任务中有 {recent_failures} 个失败，建议排查通信链路和设备状态。"

    return "设备状态正常，可继续使用。"


def _redact_sensitive(info: dict[str, Any]) -> dict[str, Any]:
    """Remove potentially sensitive fields from device info."""
    safe = {}
    for k, v in info.items():
        if k in ("token", "api_key", "password", "wifi_password", "secret"):
            safe[k] = "***"
        else:
            safe[k] = v
    return safe


def _summarize_self_check(check: dict[str, Any] | None) -> dict[str, Any] | None:
    if not check:
        return None
    return {
        "overall": check.get("overall", "unknown"),
        "timestamp": check.get("timestamp", ""),
        "checks": check.get("checks", {}),
    }
