"""Device Gateway task-store abstraction.

The default store is in-memory for local development and tests. The interface is
kept explicit so Redis/Postgres-backed stores can replace it for multi-process
or multi-node deployments without rewriting route logic.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
import itertools
from typing import Any, Protocol

from device_gateway.redis_store_helpers import _ACTIVE_STATUSES
from device_gateway.store_utils import StoreConfigMixin, StoreManager


class DeviceTaskStore(Protocol):
    backend_name: str
    shared_across_processes: bool

    def reset(self) -> None: ...

    def next_task_id(self) -> str: ...

    def create_task_state(self, task: dict[str, Any], status: str = "created") -> None: ...

    def record_motion_event(self, event: dict[str, Any]) -> dict[str, Any]: ...

    def task_snapshot(self, task_id: str) -> dict[str, Any] | None: ...

    def active_tasks_for_device(self, device_id: str) -> list[dict[str, Any]]: ...

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int: ...

    def pop_pending_tasks(self, device_id: str, limit: int = 16) -> list[dict[str, Any]]: ...

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int: ...

    def mark_task_dispatched(self, task_id: str) -> None: ...

    def ack_processing(self, device_id: str, task_id: str) -> bool: ...

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int: ...

    def pending_count(self, device_id: str | None = None) -> int: ...

    def list_tasks_for_device(self, device_id: str, status: str = "", limit: int = 20) -> list[dict[str, Any]]: ...

    def increment_retry_count(self, task_id: str) -> int: ...

    def reset_task_for_retry(self, task_id: str) -> None: ...

    def remove_pending_task(self, device_id: str, task_id: str) -> bool: ...

    def abandon_processing_task(self, device_id: str, task_id: str) -> bool: ...


class InMemoryDeviceTaskStore(StoreConfigMixin):
    backend_name = "memory"
    shared_across_processes = False

    def __init__(self) -> None:
        super().__init__()
        self._counter = itertools.count(1)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._pending_by_device: dict[str, deque[dict[str, Any]]] = {}

    def reset(self) -> None:
        with self._lock:
            self._counter = itertools.count(1)
            self._tasks.clear()
            self._pending_by_device.clear()

    def next_task_id(self) -> str:
        with self._lock:
            return f"task-{next(self._counter):06d}"

    def create_task_state(self, task: dict[str, Any], status: str = "created") -> None:
        with self._lock:
            self._tasks[task["task_id"]] = {"task": task, "status": status, "events": []}

    def record_motion_event(self, event: dict[str, Any]) -> dict[str, Any]:
        task_id = event["task_id"]
        with self._lock:
            state = self._tasks.setdefault(task_id, {"task": None, "status": "unknown", "events": []})
            state["status"] = event["phase"]
            state["events"].append(event)
            return {"task_id": task_id, "phase": event["phase"], "event_count": len(state["events"])}

    def task_snapshot(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                return None
            return {
                "task": deepcopy(state.get("task")),
                "status": state.get("status"),
                "retry_count": state.get("retry_count", 0),
                "events": deepcopy(list(state.get("events", []))),
            }

    def active_tasks_for_device(self, device_id: str) -> list[dict[str, Any]]:
        with self._lock:
            active: list[dict[str, Any]] = []
            for state in self._tasks.values():
                task = state.get("task")
                if not isinstance(task, dict) or task.get("device_id") != device_id:
                    continue
                if state.get("status") in _ACTIVE_STATUSES:
                    active.append(deepcopy(task))
            return active

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int:
        with self._lock:
            self._pending_by_device.setdefault(device_id, deque()).append(task)
            state = self._tasks.setdefault(task["task_id"], {"task": task, "status": "created", "events": []})
            state["task"] = task
            state["status"] = "queued"
            return len(self._pending_by_device[device_id])

    def pop_pending_tasks(self, device_id: str, limit: int = 16) -> list[dict[str, Any]]:
        with self._lock:
            queue = self._pending_by_device.get(device_id)
            if not queue:
                return []
            tasks: list[dict[str, Any]] = []
            while queue and len(tasks) < limit:
                task = queue.popleft()
                tasks.append(task)
                state = self._tasks.setdefault(task["task_id"], {"task": task, "status": "queued", "events": []})
                state["status"] = "dispatching"
            if not queue:
                self._pending_by_device.pop(device_id, None)
            return tasks

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int:
        with self._lock:
            queue = self._pending_by_device.setdefault(device_id, deque())
            for task in reversed(tasks):
                queue.appendleft(task)
                state = self._tasks.setdefault(task["task_id"], {"task": task, "status": "created", "events": []})
                state["task"] = task
                state["status"] = "queued"
            return len(queue)

    def mark_task_dispatched(self, task_id: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if state:
                state["status"] = "dispatched"

    def ack_processing(self, device_id: str, task_id: str) -> bool:
        return False

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int:
        return 0

    def pending_count(self, device_id: str | None = None) -> int:
        with self._lock:
            if device_id is not None:
                return len(self._pending_by_device.get(device_id, ()))
            return sum(len(queue) for queue in self._pending_by_device.values())

    def increment_retry_count(self, task_id: str) -> int:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is None:
                return 0
            count = state.get("retry_count", 0) + 1
            state["retry_count"] = count
            return count

    def reset_task_for_retry(self, task_id: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if state is not None:
                state["status"] = "queued"
                state["retry_count"] = state.get("retry_count", 0) + 1

    def remove_pending_task(self, device_id: str, task_id: str) -> bool:
        with self._lock:
            queue = self._pending_by_device.get(device_id)
            if not queue:
                return False
            for index, task in enumerate(queue):
                if str(task.get("task_id", "")) == task_id:
                    del queue[index]
                    return True
            return False

    def abandon_processing_task(self, device_id: str, task_id: str) -> bool:
        """In-memory store has no processing queue; state update is handled by callers."""
        return False

    def list_tasks_for_device(self, device_id: str, status: str = "", limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            tasks: list[dict[str, Any]] = []
            for state in self._tasks.values():
                task = state.get("task")
                if not isinstance(task, dict) or task.get("device_id") != device_id:
                    continue
                if status and state.get("status") != status:
                    continue
                tasks.append(
                    {
                        "task_id": state.get("task", {}).get("task_id", ""),
                        "status": state.get("status", "unknown"),
                        "capability": task.get("capability", ""),
                        "source": task.get("source", ""),
                    }
                )
            return tasks[:limit]


task_manager: StoreManager[DeviceTaskStore] = StoreManager[DeviceTaskStore](InMemoryDeviceTaskStore)
task_store: DeviceTaskStore = task_manager.store


def task_store_health() -> dict[str, Any]:
    return task_manager.health()


def set_task_store_for_tests(store: DeviceTaskStore) -> None:
    global task_store
    task_manager.set(store)
    task_store = task_manager.store


def configure_task_store_from_env() -> None:
    global task_store
    from config.db_config import DEVICE_REDIS_URL

    from .redis_store import RedisDeviceTaskStore

    task_manager.configure_from_env(
        "LIMA_DEVICE_TASK_STORE",
        DEVICE_REDIS_URL,
        RedisDeviceTaskStore,
        use_redis_when_url_present=True,
    )
    task_store = task_manager.store
