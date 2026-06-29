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
    encode_redis_json,
)
from device_gateway.store_utils import DeviceStoreBase

_log = logging.getLogger(__name__)


class RedisDeviceTaskStore(RedisStoreHelpers, DeviceStoreBase):
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

    def enqueue_pending_task(self, device_id: str, task: dict[str, Any]) -> int:
        task["_enqueued_at"] = self._redis.time()[0]
        queue_depth = int(self._redis.rpush(self._queue_key(device_id), encode_redis_json(task)))
        self._ensure_queue_ttl(device_id)
        default = {"task": deepcopy(task), "status": "created", "events": []}

        def _enqueue(s):
            s["task"] = deepcopy(task)
            s["status"] = "queued"

        self._cas_update(task["task_id"], _enqueue, default_state=default)
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
        tasks = [decode_redis_json(item) for item in raw_tasks]
        processing_started_at = self._redis.time()[0] if tasks else 0
        for task in tasks:
            default = {"task": deepcopy(task), "status": "queued", "events": []}

            def _dispatch(s, _t=task, _ps=processing_started_at):
                s["task"] = deepcopy(_t)
                s["status"] = "dispatching"
                s["processing_started_at"] = _ps

            self._cas_update(task["task_id"], _dispatch, default_state=default)
        return tasks

    def requeue_pending_tasks(self, device_id: str, tasks: list[dict[str, Any]]) -> int:
        if not tasks:
            return self.pending_count(device_id)
        for task in tasks:
            self._remove_processing_task(device_id, task["task_id"])
        encoded = [encode_redis_json(task) for task in reversed(tasks)]
        queue_depth = int(self._redis.lpush(self._queue_key(device_id), *encoded))
        self._ensure_queue_ttl(device_id)
        for task in tasks:
            default = {"task": deepcopy(task), "status": "created", "events": []}

            def _requeue(s, _t=task):
                s["task"] = deepcopy(_t)
                s["status"] = "queued"
                s.pop("processing_started_at", None)

            self._cas_update(task["task_id"], _requeue, default_state=default)
        return queue_depth

    def mark_task_dispatched(self, task_id: str) -> None:
        self._cas_update(task_id, lambda s: s.__setitem__("status", "dispatched"))

    def pending_count(self, device_id: str | None = None) -> int:
        if device_id is not None:
            return int(self._redis.llen(self._queue_key(device_id)))
        total = 0
        for key in self._redis.scan_iter(f"{self._prefix}:pending:*"):
            total += int(self._redis.llen(key))
        return total

    def increment_retry_count(self, task_id: str) -> int:
        # AUDIT-9-S4: CAS-protected increment to avoid losing count on concurrent writes.
        result_holder: list[int] = []

        def _bump(s):
            count = int(s.get("retry_count", 0)) + 1
            s["retry_count"] = count
            result_holder.append(count)

        self._cas_update(task_id, _bump)
        return result_holder[0] if result_holder else 0

    def reset_task_for_retry(self, task_id: str) -> None:
        # AUDIT-9-S1：与 InMemory 对齐——重置为 queued 时递增 retry_count。
        # AUDIT-9-S4：用 CAS 保护，避免并发覆盖 retry_count/status。

        def _reset(s):
            s["status"] = "queued"
            s["retry_count"] = int(s.get("retry_count", 0)) + 1

        self._cas_update(task_id, _reset)

    def remove_pending_task(self, device_id: str, task_id: str) -> bool:
        key = self._queue_key(device_id)
        for item in self._redis.lrange(key, 0, -1):
            try:
                data = decode_redis_json(item)
            except Exception as exc:
                _log.warning(
                    "remove_pending_task device=%s: corrupt queue item ignored: %s",
                    device_id,
                    exc,
                )
                continue
            if data.get("task_id") == task_id:
                return bool(self._redis.lrem(key, 1, item))
        return False

    def ack_processing(self, device_id: str, task_id: str) -> bool:
        """Remove a task from the processing queue after device ack."""
        removed = self._remove_processing_task(device_id, task_id)
        if removed:
            # AUDIT-9-S4: CAS-protected pop of processing_started_at.
            self._cas_update(task_id, lambda s: s.pop("processing_started_at", None))
        return removed

    def abandon_processing_task(self, device_id: str, task_id: str) -> bool:
        """Remove a task from the processing queue without re-queueing it."""
        removed = self._remove_processing_task(device_id, task_id)
        if removed:
            self._cas_update(
                task_id,
                lambda s: (
                    s.__setitem__("status", "dead_letter"),
                    s.pop("processing_started_at", None),
                ),
            )
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
                data = decode_redis_json(item)
                task_id = data.get("task_id", "")
                state = self._read_task_state(task_id)
                processing_started_at = 0
                if state:
                    processing_started_at = float(state.get("processing_started_at") or 0)
                processing_started_at = processing_started_at or float(
                    data.get("_processing_at") or data.get("_enqueued_at") or 0
                )
                if processing_started_at > 0 and now - processing_started_at > timeout_sec:
                    # Atomically move from processing back to pending
                    removed = self._redis.lrem(proc_key, 0, item)
                    if removed:
                        self._redis.lpush(pending_key, item)
                        self._ensure_queue_ttl(device_id)
                        if state:
                            # AUDIT-9-S4: CAS-protected status update.
                            self._cas_update(
                                task_id,
                                lambda s: (
                                    s.__setitem__("status", "queued"),
                                    s.pop("processing_started_at", None),
                                ),
                            )
                        count += 1
            except Exception as exc:
                _log.warning(
                    "recover_stale_processing device=%s: failed to recover item: %s",
                    device_id,
                    exc,
                )
                continue
        return count
