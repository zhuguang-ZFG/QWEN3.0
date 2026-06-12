"""Redis-backed Device Gateway task store."""
from __future__ import annotations

from copy import deepcopy
import json
import logging
from typing import Any

_log = logging.getLogger(__name__)


class RedisDeviceTaskStore:
    backend_name = "redis"
    shared_across_processes = True

    def __init__(self, redis_url: str, *, client: Any | None = None, key_prefix: str = "lima:device") -> None:
        if client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("redis package is required for Redis device task store") from exc
            client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._redis = client
        self._prefix = key_prefix.rstrip(":")

    def reset(self) -> None:
        keys = list(self._redis.scan_iter(f"{self._prefix}:*"))
        if keys:
            self._redis.delete(*keys)

    def next_task_id(self) -> str:
        value = int(self._redis.incr(self._key("task_counter")))
        return f"task-{value:06d}"

    def create_task_state(self, task: dict[str, Any], status: str = "created") -> None:
        state = {"task": deepcopy(task), "status": status, "events": []}
        self._write_task_state(task["task_id"], state)

    def record_motion_event(self, event: dict[str, Any]) -> dict[str, Any]:
        task_id = event["task_id"]
        state = self._read_task_state(task_id) or {"task": None, "status": "unknown", "events": []}
        events = list(state.get("events", []))
        events.append(deepcopy(event))
        state["events"] = events
        state["status"] = event["phase"]
        self._write_task_state(task_id, state)
        return {"task_id": task_id, "phase": event["phase"], "event_count": len(events)}

    def task_snapshot(self, task_id: str) -> dict[str, Any] | None:
        state = self._read_task_state(task_id)
        if state is None:
            return None
        return {
            "task": deepcopy(state.get("task")),
            "status": state.get("status"),
            "events": deepcopy(list(state.get("events", []))),
        }

    def active_tasks_for_device(self, device_id: str) -> list[dict[str, Any]]:
        active: list[dict[str, Any]] = []
        raw_states = self._redis.hgetall(self._key("tasks"))
        values = raw_states.values() if isinstance(raw_states, dict) else raw_states
        for raw_state in values:
            try:
                state = self._decode(raw_state)
            except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError) as exc:
                _log.warning("redis active task decode failed: %s", type(exc).__name__)
                continue
            task = state.get("task")
            if not isinstance(task, dict) or task.get("device_id") != device_id:
                continue
            if state.get("status") in _ACTIVE_STATUSES:
                active.append(deepcopy(task))
        return active

    def list_tasks_for_device(
        self,
        device_id: str,
        status: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        raw_states = self._redis.hgetall(self._key("tasks"))
        values = raw_states.values() if isinstance(raw_states, dict) else raw_states
        for raw_state in values:
            try:
                state = self._decode(raw_state)
            except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError) as exc:
                _log.warning("redis task list decode failed: %s", type(exc).__name__)
                continue
            task = state.get("task")
            if not isinstance(task, dict) or task.get("device_id") != device_id:
                continue
            if status and state.get("status") != status:
                continue
            tasks.append(
                {
                    "task_id": task.get("task_id", ""),
                    "status": state.get("status", "unknown"),
                    "capability": task.get("capability", ""),
                    "source": task.get("source", ""),
                }
            )
            if len(tasks) >= limit:
                break
        return tasks

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int:
        task["_enqueued_at"] = self._redis.time()[0]
        queue_depth = int(self._redis.rpush(self._queue_key(device_id), self._encode(task)))
        state = self._read_task_state(task["task_id"]) or {"task": task, "status": "created", "events": []}
        state["task"] = deepcopy(task)
        state["status"] = "queued"
        self._write_task_state(task["task_id"], state)
        return queue_depth

    def pop_pending_tasks(self, device_id: str, limit: int = 16) -> list[dict[str, Any]]:
        """Atomically move tasks from pending to processing queue using LMOVE.

        Tasks are moved to a processing queue. Call ack_processing() after
        the device confirms receipt, or let recover_stale_processing() re-queue
        orphaned tasks after a timeout.
        """
        raw_tasks = self._lmove_many(
            self._queue_key(device_id),
            self._processing_key(device_id),
            limit,
        )
        tasks = [self._decode(item) for item in raw_tasks]
        processing_started_at = self._redis.time()[0] if tasks else 0
        for task in tasks:
            state = self._read_task_state(task["task_id"]) or {
                "task": task, "status": "queued", "events": [],
            }
            state["task"] = deepcopy(task)
            state["status"] = "dispatching"
            state["processing_started_at"] = processing_started_at
            self._write_task_state(task["task_id"], state)
        return tasks

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int:
        if not tasks:
            return self.pending_count(device_id)
        for task in tasks:
            self._remove_processing_task(device_id, task["task_id"])
        encoded = [self._encode(task) for task in reversed(tasks)]
        queue_depth = int(self._redis.lpush(self._queue_key(device_id), *encoded))
        for task in tasks:
            state = self._read_task_state(task["task_id"]) or {"task": task, "status": "created", "events": []}
            state["task"] = deepcopy(task)
            state["status"] = "queued"
            state.pop("processing_started_at", None)
            self._write_task_state(task["task_id"], state)
        return queue_depth

    def mark_task_dispatched(self, task_id: str) -> None:
        state = self._read_task_state(task_id)
        if state is not None:
            state["status"] = "dispatched"
            self._write_task_state(task_id, state)

    def pending_count(self, device_id: str | None = None) -> int:
        if device_id is not None:
            return int(self._redis.llen(self._queue_key(device_id)))
        total = 0
        for key in self._redis.scan_iter(f"{self._prefix}:pending:*"):
            total += int(self._redis.llen(key))
        return total

    def _key(self, suffix: str) -> str:
        return f"{self._prefix}:{suffix}"

    def ack_processing(self, device_id: str, task_id: str) -> bool:
        """Remove a task from the processing queue after device ack."""
        removed = self._remove_processing_task(device_id, task_id)
        if removed:
            state = self._read_task_state(task_id)
            if state:
                state.pop("processing_started_at", None)
                self._write_task_state(task_id, state)
        return removed

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int:
        """Re-queue tasks stuck in processing queue for longer than timeout_sec.

        Returns count of tasks re-queued. Call periodically from a background
        task or health check to recover from process crashes.
        """
        proc_key = self._processing_key(device_id)
        pending_key = self._queue_key(device_id)
        now = self._redis.time()[0]  # Redis server time in seconds
        count = 0
        # Peek all processing items
        items = self._redis.lrange(proc_key, 0, -1)
        for item in items:
            try:
                data = self._decode(item)
                task_id = data.get("task_id", "")
                state = self._read_task_state(task_id)
                processing_started_at = 0
                if state:
                    processing_started_at = float(state.get("processing_started_at") or 0)
                processing_started_at = processing_started_at or float(data.get("_processing_at") or data.get("_enqueued_at") or 0)
                if processing_started_at > 0 and now - processing_started_at > timeout_sec:
                    # Atomically move from processing back to pending
                    removed = self._redis.lrem(proc_key, 0, item)
                    if removed:
                        self._redis.lpush(pending_key, item)
                        if state:
                            state["status"] = "queued"
                            state.pop("processing_started_at", None)
                            self._write_task_state(task_id, state)
                        count += 1
            except Exception:
                continue
        return count

    def _queue_key(self, device_id: str) -> str:
        return self._key(f"pending:{device_id}")

    def _processing_key(self, device_id: str) -> str:
        return self._key(f"processing:{device_id}")

    def _lmove_many(self, src: str, dst: str, limit: int) -> list[str]:
        """Atomically move items from src list to dst list using LMOVE."""
        results = []
        for _ in range(limit):
            item = self._redis.lmove(src, dst, "LEFT", "LEFT")
            if item is None:
                break
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            results.append(item)
        return results

    def _remove_processing_task(self, device_id: str, task_id: str) -> bool:
        key = self._processing_key(device_id)
        for item in self._redis.lrange(key, 0, -1):
            try:
                data = self._decode(item)
            except Exception:
                continue
            if data.get("task_id") == task_id:
                return bool(self._redis.lrem(key, 1, item))
        return False

    def _read_task_state(self, task_id: str) -> dict[str, Any] | None:
        raw = self._redis.hget(self._key("tasks"), task_id)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None

    def _write_task_state(self, task_id: str, state: dict[str, Any]) -> None:
        self._redis.hset(self._key("tasks"), task_id, self._encode(state))

    def _lpop_many(self, key: str, limit: int) -> list[str]:
        popped = self._redis.lpop(key, count=limit)
        if popped is None:
            return []
        if isinstance(popped, list):
            return popped
        return [popped]

    @staticmethod
    def _encode(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(value: str | bytes) -> dict[str, Any]:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        data = json.loads(value)
        if not isinstance(data, dict):
            raise RuntimeError(f"expected Redis JSON object, got: {data!r}")
        return data


_ACTIVE_STATUSES = frozenset({"dispatched", "running", "processing", "progress", "accepted"})
