"""Append-only in-memory ledger store for device task events."""

from __future__ import annotations

from copy import deepcopy
import threading
from typing import Any

from .events import DuplicateLedgerEvent, LedgerEvent


class InMemoryLedgerStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._event_ids: set[str] = set()
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._event_ids.clear()

    def append_event(self, event: LedgerEvent) -> None:
        with self._lock:
            if event.event_id in self._event_ids:
                raise DuplicateLedgerEvent(f"duplicate ledger event id: {event.event_id}")
            self._event_ids.add(event.event_id)
            self._events.append(deepcopy(event))

    def events_for_task(self, task_id: str) -> list[LedgerEvent]:
        with self._lock:
            return [deepcopy(event) for event in self._events if event.task_id == task_id]

    def replay_task(self, task_id: str) -> dict[str, Any]:
        task: dict[str, Any] | None = None
        device_id = ""
        status = "unknown"
        terminal_event: dict[str, Any] | None = None
        events = self.events_for_task(task_id)

        for event in events:
            device_id = event.device_id or device_id
            if event.event_type == "task_created":
                task = deepcopy(event.payload.get("task"))
                status = str(event.payload.get("status", "created"))
            elif event.event_type == "task_dispatched":
                status = "dispatched"
            elif event.event_type == "motion_event":
                motion_event = _payload_event(event.payload)
                status = str(motion_event.get("phase", status))
            elif event.event_type == "task_terminal":
                terminal_event = _payload_event(event.payload)
                status = str(terminal_event.get("phase", status))

        return {
            "task_id": task_id,
            "device_id": device_id,
            "status": status,
            "task": task,
            "terminal_event": terminal_event,
            "event_count": len(events),
            "events": [event.to_dict() for event in events],
        }


def _payload_event(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("motion_event"), dict):
        return deepcopy(payload["motion_event"])
    if isinstance(payload.get("terminal_event"), dict):
        return deepcopy(payload["terminal_event"])
    return deepcopy(payload)


ledger_store = InMemoryLedgerStore()
