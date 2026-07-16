"""Redis-backed Device Gateway task store."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from config.settings import DEVICE
from device_gateway.redis_store_helpers import (
    RedisStoreHelpers,
    _ACTIVE_STATUSES,
    connect_redis,
    decode_redis_json,
)
from device_gateway.store_utils import DeviceStoreBase
from device_gateway.redis_store_index import RedisTaskIndexMixin
from device_gateway.redis_store_queue import RedisStoreQueueMixin
from device_gateway.redis_store_recover import RedisStoreRecoverMixin

_log = logging.getLogger(__name__)


class RedisDeviceTaskStore(
    RedisTaskIndexMixin, RedisStoreQueueMixin, RedisStoreHelpers, RedisStoreRecoverMixin, DeviceStoreBase
):
    backend_name = "redis"
    shared_across_processes = True

    def __init__(self, redis_url: str, *, client: Any | None = None, key_prefix: str = "lima:device") -> None:
        self._redis, self._prefix = connect_redis(
            redis_url, "RedisDeviceTaskStore", client=client, key_prefix=key_prefix
        )

    def reset(self) -> None:
        keys = list(self._redis.scan_iter(f"{self._prefix}:*"))
        if keys:
            self._redis.delete(*keys)

    def ping(self) -> None:
        """Liveness check for the underlying Redis connection."""
        self._redis.ping()

    def close(self) -> None:
        """Close the underlying Redis connection pool."""
        self._redis.close()

    def next_task_id(self) -> str:
        value = int(self._redis.incr(self._key("task_counter")))
        return f"task-{value:06d}"

    def create_task_state(self, task: dict[str, Any], status: str = "created") -> None:
        state = {"task": deepcopy(task), "status": status, "events": []}
        self._write_task_state(task["task_id"], state)

    def record_motion_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Append a motion event atomically (AUDIT-9-S4).

        Uses a Lua script to append the event and update status inside Redis,
        avoiding the lost-update problem of concurrent read-modify-write cycles.
        """
        from device_gateway.redis_cas import append_event_atomic

        task_id = event["task_id"]
        phase = event.get("phase", "")
        updated = append_event_atomic(
            self._redis, self._key("tasks"), task_id, event, DEVICE.redis_task_ttl, new_status=phase
        )
        if updated is None:
            # Task missing — create a stub state (preserves original behavior).
            updated = {"task": None, "status": phase, "events": [deepcopy(event)]}
            self._write_task_state(task_id, updated)
        events = updated.get("events", [])
        return {"task_id": task_id, "phase": phase, "event_count": len(events)}

    def task_snapshot(self, task_id: str) -> dict[str, Any] | None:
        state = self._read_task_state(task_id)
        if state is None:
            return None
        return {
            "task": deepcopy(state.get("task")),
            "status": state.get("status"),
            "retry_count": state.get("retry_count", 0),
            "events": deepcopy(list(state.get("events", []))),
            "_version": state.get("_version", 0),
        }

    def active_tasks_for_device(self, device_id: str) -> list[dict[str, Any]]:
        if self._task_index_enabled():
            return self._active_tasks_indexed(device_id)
        return self._active_tasks_hgetall(device_id)

    def _active_tasks_hgetall(self, device_id: str) -> list[dict[str, Any]]:
        active: list[dict[str, Any]] = []
        raw_states = self._redis.hgetall(self._key("tasks"))
        values = raw_states.values() if isinstance(raw_states, dict) else raw_states
        for raw_state in values:
            try:
                state = decode_redis_json(raw_state)
            except (UnicodeDecodeError, RuntimeError) as exc:
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
        if self._task_index_enabled():
            return self._list_tasks_indexed(device_id, status, limit)
        return self._list_tasks_hgetall(device_id, status, limit)

    def _list_tasks_hgetall(
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
                state = decode_redis_json(raw_state)
            except (UnicodeDecodeError, RuntimeError) as exc:
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
