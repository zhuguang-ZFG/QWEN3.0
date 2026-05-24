"""Redis-backed Device Gateway task store."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


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

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int:
        queue_depth = int(self._redis.rpush(self._queue_key(device_id), self._encode(task)))
        state = self._read_task_state(task["task_id"]) or {"task": task, "status": "created", "events": []}
        state["task"] = deepcopy(task)
        state["status"] = "queued"
        self._write_task_state(task["task_id"], state)
        return queue_depth

    def pop_pending_tasks(self, device_id: str, limit: int = 16) -> list[dict[str, Any]]:
        raw_tasks = self._lpop_many(self._queue_key(device_id), limit)
        tasks = [self._decode(item) for item in raw_tasks]
        for task in tasks:
            state = self._read_task_state(task["task_id"]) or {"task": task, "status": "queued", "events": []}
            state["task"] = deepcopy(task)
            state["status"] = "dispatching"
            self._write_task_state(task["task_id"], state)
        return tasks

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int:
        if not tasks:
            return self.pending_count(device_id)
        encoded = [self._encode(task) for task in reversed(tasks)]
        queue_depth = int(self._redis.lpush(self._queue_key(device_id), *encoded))
        for task in tasks:
            state = self._read_task_state(task["task_id"]) or {"task": task, "status": "created", "events": []}
            state["task"] = deepcopy(task)
            state["status"] = "queued"
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

    def _queue_key(self, device_id: str) -> str:
        return self._key(f"pending:{device_id}")

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
