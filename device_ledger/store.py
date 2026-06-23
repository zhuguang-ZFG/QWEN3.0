"""Append-only ledger store backends for device task events."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from device_gateway.store_utils import DeviceStoreBase, StoreConfigMixin, StoreManager

from .events import DuplicateLedgerEvent, LedgerEvent


class LedgerStoreBackend(Protocol):
    backend_name: str
    shared_across_processes: bool

    def reset(self) -> None: ...

    def append_event(self, event: LedgerEvent) -> None: ...

    def events_for_task(self, task_id: str) -> list[LedgerEvent]: ...

    def events_for_device(self, device_id: str) -> list[LedgerEvent]: ...

    def replay_task(self, task_id: str) -> dict[str, Any]: ...


class InMemoryLedgerStore(StoreConfigMixin):
    backend_name = "memory"
    shared_across_processes = False

    def __init__(self) -> None:
        super().__init__()
        self._events: list[LedgerEvent] = []
        self._event_ids: set[str] = set()

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

    def events_for_device(self, device_id: str) -> list[LedgerEvent]:
        with self._lock:
            return [deepcopy(event) for event in self._events if event.device_id == device_id]

    def replay_task(self, task_id: str) -> dict[str, Any]:
        return _replay_from_events(self.events_for_task(task_id), task_id)


ledger_manager: StoreManager[LedgerStoreBackend] = StoreManager[LedgerStoreBackend](InMemoryLedgerStore)
ledger_store: LedgerStoreBackend = ledger_manager.store


def ledger_store_health() -> dict[str, Any]:
    return ledger_manager.health()


def set_ledger_store_for_tests(store: LedgerStoreBackend) -> None:
    global ledger_store
    ledger_manager.set(store)
    ledger_store = ledger_manager.store


def configure_ledger_store_from_env() -> None:
    global ledger_store
    from config.db_config import DEVICE_REDIS_URL

    from device_ledger.redis_store import RedisLedgerStore

    ledger_manager.configure_from_env(
        "LIMA_DEVICE_LEDGER_STORE",
        DEVICE_REDIS_URL,
        RedisLedgerStore,
    )
    ledger_store = ledger_manager.store


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
