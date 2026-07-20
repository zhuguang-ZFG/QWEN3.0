"""Pending/processing queue operations for RedisDeviceTaskStore."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from device_gateway.redis_store_helpers import (
    QUEUED_MAX_AGE_SEC,
    decode_redis_json,
    encode_redis_json,
    validate_task_schema,
)

_log = logging.getLogger(__name__)


def _strict_dispatch_gen() -> bool:
    """GW-R3-2 rollout gate: reject gen-less acks only when firmware echoes gen.

    Off by default — current firmware omits dispatch_gen (B5 pending), so
    strict rejection would loop every recovered task. Read lazily so the flag
    can be flipped without a settings re-import.
    """
    from config.settings import FLAGS

    return bool(getattr(FLAGS, "strict_dispatch_gen", False))


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

    def _gate_popped_tasks(self, device_id: str, raw_tasks: list[str]) -> list[dict[str, Any]]:
        """SEC-06: gate popped tasks against the capability/field allowlist.

        A malicious Redis RPUSH bypasses HTTP validation; drop rejected tasks
        from the processing queue so they are never forwarded to firmware, and
        mark their state failed (GW-WA/WB) so they cannot linger as active
        "queued" ghosts that keep the device busy while callers saw success.
        """
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
            dropped_id = task.get("task_id")
            if dropped_id:

                def _mark_failed(s):
                    s["status"] = "failed"
                    s["error"] = "sec06_capability_rejected"

                self._cas_update(dropped_id, _mark_failed)
        return tasks

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
        tasks = self._gate_popped_tasks(device_id, raw_tasks)
        processing_started_at = self._redis.time()[0] if tasks else 0
        for task in tasks:
            default = {"task": deepcopy(task), "status": "queued", "events": []}

            def _dispatch(s, _t=task, _ps=processing_started_at):
                s["task"] = deepcopy(_t)
                s["status"] = "dispatching"
                s["processing_started_at"] = _ps
                # Anti-double-spend cleanup: this is a fresh dispatch, so a
                # subsequent ack is legitimate. Without this, recovered_at
                # persisted forever and ack_processing rejected every ack
                # after the first recovery (W4, 2026-07-20 review).
                s.pop("recovered_at", None)

            state = self._cas_update(task["task_id"], _dispatch, default_state=default)
            # GW-WC: stamp the dispatch generation onto the outgoing task so
            # the eventual ack can prove it belongs to this dispatch.
            task["_dispatch_gen"] = int(state.get("dispatch_gen", 0)) if state else 0
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

    def ack_processing(self, device_id: str, task_id: str, dispatch_gen: int | None = None) -> bool:
        """Remove a task from the processing queue after device ack.

        Anti-double-spend (GW-WC): when the caller provides ``dispatch_gen``
        (stamped on the task at pop time), it must match the stored
        generation — a re-dispatch bumps the generation, so acks from stale
        pre-recovery workers are rejected even after recovered_at is cleared.
        Callers without a generation fall back to the recovered_at check.
        """
        state = self._read_task_state(task_id)
        if state is not None:
            current_gen = int(state.get("dispatch_gen", 0))
            if dispatch_gen is not None:
                if int(dispatch_gen) != current_gen:
                    _log.warning(
                        "ack_processing rejected: task %s stale dispatch_gen %s != %s",
                        task_id,
                        dispatch_gen,
                        current_gen,
                    )
                    # Do NOT touch the processing queue: after a re-dispatch the
                    # entry there belongs to the current generation's worker.
                    return False
            elif current_gen > 0 and _strict_dispatch_gen():
                # GW-R3-2: after recover/re-dispatch, gen-less acks must not
                # LREM the current processing entry (stale workers omit gen).
                # Gated: today firmware omits dispatch_gen, so strict mode would
                # reject every legitimate recovered-task ack (loop). Enable only
                # once motion_event echoes the generation (B5).
                _log.warning(
                    "ack_processing rejected: task %s missing dispatch_gen (current=%s)",
                    task_id,
                    current_gen,
                )
                return False
        if state and state.get("recovered_at"):
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

    def expire_stale_queued(self, device_id: str, max_age_sec: float = QUEUED_MAX_AGE_SEC) -> int:
        """GW-WG: age out queued tasks that no delivery channel will ever pop.

        Removes over-age items from the pending queue and marks their state
        "expired" (terminal) so they stop holding the device "busy" forever.
        """
        queue_key = self._queue_key(device_id)
        now = float(self._redis.time()[0])
        count = 0
        for item in self._redis.lrange(queue_key, 0, -1):
            try:
                task = decode_redis_json(item)
                enqueued_at = float(task.get("_enqueued_at") or 0)
            except Exception as exc:
                _log.warning("expire_stale_queued device=%s: corrupt queue item ignored: %s", device_id, exc)
                continue
            if enqueued_at <= 0 or now - enqueued_at <= max_age_sec:
                continue
            if not self._redis.lrem(queue_key, 1, item):
                continue
            task_id = task.get("task_id")
            if task_id:

                def _expire(s):
                    if s.get("status") == "queued":
                        s["status"] = "expired"

                self._cas_update(task_id, _expire)
            count += 1
            _log.warning(
                "GW-WG: expired stale queued task device=%s task=%s age=%.0fs",
                device_id,
                task_id,
                now - enqueued_at,
            )
        return count

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
