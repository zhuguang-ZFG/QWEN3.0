"""Pending/processing queue operations for RedisDeviceTaskStore."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from device_gateway.redis_store_helpers import decode_redis_json, encode_redis_json, validate_task_schema

_log = logging.getLogger(__name__)


class RedisStoreQueueMixin:
    """Queue lifecycle methods extracted to keep redis_store.py under the size gate."""

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
        # SEC-06: gate every popped task against the capability/field allowlist.
        # A malicious Redis RPUSH bypasses HTTP validation; drop rejected tasks
        # from the processing queue so they are never forwarded to firmware.
        tasks: list[dict[str, Any]] = []
        for item in raw_tasks:
            task = decode_redis_json(item)
            if validate_task_schema(task):
                tasks.append(task)
                continue
            _log.warning(
                "SEC-06: dropped invalid task on pop device=%s capability=%r task_id=%r",
                device_id,
                task.get("capability"),
                task.get("task_id"),
            )
            self._redis.lrem(self._processing_key(device_id), 1, item)
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
        # AUDIT-9-S1: align with InMemory — increment retry_count when resetting to queued.
        # AUDIT-9-S4: CAS protects concurrent overwrite of retry_count/status.

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
        """Remove a task from the processing queue after device ack.

        Anti-double-spend: if task was already recovered back to pending,
        reject this late ack so downstream never fires a duplicate completion.
        """
        state = self._read_task_state(task_id)
        if state and state.get("recovered_at") and state.get("status") != "processing":
            _log.warning(
                "ack_processing rejected: task %s already recovered (status=%s)",
                task_id,
                state.get("status"),
            )
            self._remove_processing_task(device_id, task_id)  # cleanup stale entry
            return False
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
