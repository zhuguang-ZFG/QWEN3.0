"""Append-only ledger store backends for device task events."""

from __future__ import annotations

import os
from copy import deepcopy
import threading
from typing import Any, Protocol

from .events import DuplicateLedgerEvent, LedgerEvent


class LedgerStoreBackend(Protocol):
    backend_name: str
    shared_across_processes: bool

    def reset(self) -> None:
        ...

    def append_event(self, event: LedgerEvent) -> None:
        ...

    def events_for_task(self, task_id: str) -> list[LedgerEvent]:
        ...

    def replay_task(self, task_id: str) -> dict[str, Any]:
        ...


class InMemoryLedgerStore:
    backend_name = "memory"
    shared_across_processes = False

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
        return _replay_from_events(self.events_for_task(task_id), task_id)


ledger_store: LedgerStoreBackend = InMemoryLedgerStore()


def ledger_store_health() -> dict[str, Any]:
    return {
        "backend": getattr(ledger_store, "backend_name", ledger_store.__class__.__name__),
        "shared_across_processes": bool(getattr(ledger_store, "shared_across_processes", False)),
    }


def set_ledger_store_for_tests(store: LedgerStoreBackend) -> None:
    global ledger_store
    ledger_store = store


def configure_ledger_store_from_env() -> None:
    global ledger_store
    backend = os.environ.get("LIMA_DEVICE_LEDGER_STORE", "").strip().lower()
    redis_url = os.environ.get("LIMA_DEVICE_REDIS_URL", "").strip()
    if backend == "redis":
        if not redis_url:
            raise RuntimeError("LIMA_DEVICE_REDIS_URL is required when LIMA_DEVICE_LEDGER_STORE=redis")
        from device_ledger.redis_store import RedisLedgerStore

        ledger_store = RedisLedgerStore(redis_url)
    else:
        ledger_store = InMemoryLedgerStore()


def _replay_from_events(events: list[LedgerEvent], task_id: str) -> dict[str, Any]:
    task: dict[str, Any] | None = None
    device_id = ""
    status = "unknown"
    terminal_event: dict[str, Any] | None = None

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
