"""Read-only projections replayed from the device event ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from device_ledger.store import ledger_store


class TaskProjection:
    """Rebuild a task's current state by replaying its ledger events."""

    def rebuild_state(self, task_id: str) -> dict[str, Any]:
        events = sorted(ledger_store.events_for_task(task_id), key=lambda e: e.created_at or "")
        state: dict[str, Any] = {
            "task_id": task_id,
            "device_id": "",
            "status": "unknown",
            "progress": 0,
            "error": None,
            "created_at": "",
            "last_event_at": "",
            "event_count": len(events),
        }
        for event in events:
            if event.device_id:
                state["device_id"] = event.device_id
            if event.created_at:
                if not state["created_at"]:
                    state["created_at"] = event.created_at
                state["last_event_at"] = event.created_at
            state["status"] = _status_after_event(event, state["status"])
            progress = _event_progress(event)
            if progress is not None:
                state["progress"] = progress
            error = _event_error(event)
            if error is not None:
                state["error"] = error
        return state

    def timeline(self, task_id: str) -> list[dict[str, Any]]:
        events = sorted(ledger_store.events_for_task(task_id), key=lambda e: e.created_at or "")
        return [event.to_dict() for event in events]

    def task_duration(self, task_id: str) -> dict[str, Any] | None:
        events = sorted(ledger_store.events_for_task(task_id), key=lambda e: e.created_at or "")
        if not events:
            return None
        created = _first_event_ts(events, "task_created")
        dispatched = _first_event_ts(events, "task_dispatched")
        acknowledged = _first_event_ts(events, "task_acknowledged")
        terminal = _last_event_ts(events, "task_terminal")

        total_ms = _delta_ms(created, terminal)
        queue_ms = _delta_ms(created, dispatched)
        dispatch_ms = _delta_ms(dispatched, acknowledged)
        execute_ms = _delta_ms(acknowledged, terminal)

        if total_ms is None and queue_ms is None and dispatch_ms is None and execute_ms is None:
            return None
        return {
            "total_ms": total_ms,
            "queue_ms": queue_ms,
            "dispatch_ms": dispatch_ms,
            "execute_ms": execute_ms,
        }


class DeviceProjection:
    """Aggregate statistics for a device by replaying its ledger events."""

    def device_summary(self, device_id: str, limit: int = 100) -> dict[str, Any]:
        events = sorted(ledger_store.events_for_device(device_id), key=lambda e: e.created_at or "")
        if limit > 0:
            events = events[-limit:]
        task_ids: set[str] = set()
        completed = 0
        failed = 0
        last_activity = ""
        for event in events:
            if event.task_id and event.event_type not in {"device_connected", "device_disconnected"}:
                task_ids.add(event.task_id)
            if event.created_at:
                last_activity = event.created_at
            if event.event_type == "task_terminal":
                phase = _payload_phase(event.payload)
                if phase == "done":
                    completed += 1
                elif phase == "failed":
                    failed += 1
        terminal_total = completed + failed
        success_rate = round(completed / terminal_total, 4) if terminal_total else 0.0
        return {
            "device_id": device_id,
            "total_events": len(events),
            "unique_tasks": len(task_ids),
            "completed": completed,
            "failed": failed,
            "success_rate": success_rate,
            "last_activity": last_activity,
        }


task_projection = TaskProjection()
device_projection = DeviceProjection()


def _status_after_event(event: Any, current: str) -> str:
    event_type = event.event_type
    payload = event.payload or {}
    if event_type == "task_created":
        return str(payload.get("status", "created"))
    if event_type == "task_dispatched":
        return "dispatched"
    if event_type == "task_acknowledged":
        return "acknowledged"
    if event_type == "task_progress":
        return "running"
    if event_type == "task_paused":
        return "paused"
    if event_type == "task_resumed":
        return "resumed"
    if event_type in {"motion_event", "task_terminal"}:
        phase = _payload_phase(payload)
        if phase:
            return phase
    return current


def _payload_phase(payload: dict[str, Any]) -> str:
    event = payload.get("motion_event") or payload.get("terminal_event") or payload
    if isinstance(event, dict):
        return str(event.get("phase", ""))
    return ""


def _event_progress(event: Any) -> int | None:
    if event.event_type == "task_progress":
        progress = event.payload.get("progress")
        if isinstance(progress, (int, float)):
            return int(progress)
    if event.event_type == "motion_event":
        motion = event.payload.get("motion_event")
        if isinstance(motion, dict):
            progress = motion.get("progress")
            if isinstance(progress, (int, float)):
                return int(progress)
    return None


def _event_error(event: Any) -> dict[str, Any] | str | None:
    if event.event_type in {"motion_event", "task_terminal"}:
        source = event.payload.get("motion_event") or event.payload.get("terminal_event") or event.payload
        if isinstance(source, dict):
            error = source.get("error")
            if error is not None:
                return error
            code = source.get("error_code")
            message = source.get("error_message")
            if code is not None or message is not None:
                return {"code": code, "message": message}
    return None


def _first_event_ts(events: list[Any], event_type: str) -> datetime | None:
    for event in events:
        if event.event_type == event_type and event.created_at:
            ts = _parse_iso(event.created_at)
            if ts is not None:
                return ts
    return None


def _last_event_ts(events: list[Any], event_type: str) -> datetime | None:
    for event in reversed(events):
        if event.event_type == event_type and event.created_at:
            ts = _parse_iso(event.created_at)
            if ts is not None:
                return ts
    return None


def _delta_ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    delta = end - start
    return int(delta.total_seconds() * 1000)


def _parse_iso(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None
