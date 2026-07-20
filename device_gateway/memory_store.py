"""In-memory implementation of the device task store."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
import itertools
import time as _time
from typing import Any

from device_gateway.redis_store_helpers import _ACTIVE_STATUSES, QUEUED_MAX_AGE_SEC
from device_gateway.store_utils import StoreConfigMixin


class InMemoryDeviceTaskStore(StoreConfigMixin):
    backend_name = "memory"
    shared_across_processes = False

    def __init__(self) -> None:
        super().__init__()
        self._counter = itertools.count(1)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._pending_by_device: dict[str, deque[dict[str, Any]]] = {}
        # AUDIT-9-S3: processing queue mirrors Redis LMOVE semantics (ack/recover/abandon tests).
        self._processing_by_device: dict[str, dict[str, dict[str, Any]]] = {}

    def reset(self) -> None:
        with self._lock:
            self._counter = itertools.count(1)
            self._tasks.clear()
            self._pending_by_device.clear()
            self._processing_by_device.clear()

    def ping(self) -> None:
        return None

    def close(self) -> None:
        return None

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
        # GW-WG: lazily reclaim over-age queued tasks where "busy" is computed.
        self.expire_stale_queued(device_id)
        with self._lock:
            active: list[dict[str, Any]] = []
            for state in self._tasks.values():
                task = state.get("task")
                if not isinstance(task, dict) or task.get("device_id") != device_id:
                    continue
                if state.get("status") in _ACTIVE_STATUSES:
                    active.append(deepcopy(task))
            return active

    def expire_stale_queued(self, device_id: str, max_age_sec: float = QUEUED_MAX_AGE_SEC) -> int:
        """GW-WG: age out queued tasks that no delivery channel will ever pop."""
        with self._lock:
            queue = self._pending_by_device.get(device_id)
            if not queue:
                return 0
            now = _time.time()
            kept: deque[dict[str, Any]] = deque()
            count = 0
            while queue:
                task = queue.popleft()
                enqueued_at = float(task.get("_enqueued_at") or 0)
                if enqueued_at > 0 and now - enqueued_at > max_age_sec:
                    state = self._tasks.get(str(task.get("task_id", "")))
                    if state and state.get("status") == "queued":
                        state["status"] = "expired"
                    count += 1
                    continue
                kept.append(task)
            if kept:
                self._pending_by_device[device_id] = kept
            else:
                self._pending_by_device.pop(device_id, None)
            return count

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int:
        with self._lock:
            # Mirror the Redis backend's enqueue timestamp (used by GW-WG expiry).
            task["_enqueued_at"] = _time.time()
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
            processing = self._processing_by_device.setdefault(device_id, {})
            now = _time.time()
            while queue and len(tasks) < limit:
                task = queue.popleft()
                tasks.append(task)
                tid = task["task_id"]
                processing[tid] = {"task": task, "processing_started_at": now}
                state = self._tasks.setdefault(tid, {"task": task, "status": "queued", "events": []})
                state["status"] = "dispatching"
                state["processing_started_at"] = now
                # GW-WC: stamp the dispatch generation so acks can be matched
                # against the generation active at dispatch time.
                task["_dispatch_gen"] = int(state.get("dispatch_gen", 0))
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

    def ack_processing(self, device_id: str, task_id: str, dispatch_gen: int | None = None) -> bool:
        with self._lock:
            processing = self._processing_by_device.get(device_id, {})
            state = self._tasks.get(task_id)
            # GW-WC / GW-R3-2: reject stale or gen-less acks after re-dispatch.
            # Leave the processing entry alone — it belongs to the current gen.
            if state is not None:
                current_gen = int(state.get("dispatch_gen", 0))
                if dispatch_gen is not None:
                    if int(dispatch_gen) != current_gen:
                        return False
                elif current_gen > 0:
                    return False
            entry = processing.pop(task_id, None)
            if entry is None:
                return False
            if state:
                state.pop("processing_started_at", None)
            return True

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int:
        with self._lock:
            processing = self._processing_by_device.get(device_id)
            if not processing:
                return 0
            now = _time.time()
            queue = self._pending_by_device.setdefault(device_id, deque())
            recovered = []
            for tid, entry in list(processing.items()):
                started = float(entry.get("processing_started_at", 0))
                if started > 0 and now - started > timeout_sec:
                    processing.pop(tid, None)
                    queue.appendleft(entry["task"])
                    state = self._tasks.get(tid)
                    if state:
                        state["status"] = "queued"
                        # GW-WC: bump generation so stale acks stay rejected.
                        state["dispatch_gen"] = int(state.get("dispatch_gen", 0)) + 1
                        state.pop("processing_started_at", None)
                    recovered.append(tid)
            return len(recovered)

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
        # AUDIT-9-S3: now removes from processing queue + marks dead_letter.
        with self._lock:
            processing = self._processing_by_device.get(device_id, {})
            entry = processing.pop(task_id, None)
            if entry is None:
                return False
            state = self._tasks.get(task_id)
            if state:
                state["status"] = "dead_letter"
                state.pop("processing_started_at", None)
            return True

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

    def list_inflight_task_ids(self, limit: int = 1000) -> list[str]:
        with self._lock:
            ids: list[str] = []
            for task_id, state in self._tasks.items():
                if state.get("status") in _ACTIVE_STATUSES:
                    ids.append(task_id)
                    if len(ids) >= limit:
                        break
            return ids
