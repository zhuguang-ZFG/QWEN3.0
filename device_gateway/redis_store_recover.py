"""RedisDeviceTaskStore 的 stale processing 恢复 mixin — 从 redis_store.py 拆出以控制行数。

依赖主类的 self._redis / self._processing_key / self._queue_key /
self._read_task_state / self._ensure_queue_ttl / self._cas_update。
"""

from __future__ import annotations

import logging

from device_gateway.redis_store_helpers import decode_redis_json

_log = logging.getLogger(__name__)


class RedisStoreRecoverMixin:
    """Re-queue tasks stuck in processing queue for longer than timeout_sec.

    Returns count of tasks re-queued. Call periodically from a background
    task or health check to recover from process crashes.
    """

    def recover_stale_processing(self, device_id: str, timeout_sec: float = 120.0) -> int:
        proc_key = self._processing_key(device_id)  # type: ignore[attr-defined]
        pending_key = self._queue_key(device_id)  # type: ignore[attr-defined]
        now = self._redis.time()[0]  # Redis server time in seconds  # type: ignore[attr-defined]
        count = 0
        # Peek all processing items
        items = self._redis.lrange(proc_key, 0, -1)  # type: ignore[attr-defined]
        for item in items:
            try:
                data = decode_redis_json(item)
                task_id = data.get("task_id", "")
                state = self._read_task_state(task_id)  # type: ignore[attr-defined]
                processing_started_at = 0
                if state:
                    processing_started_at = float(state.get("processing_started_at") or 0)
                processing_started_at = processing_started_at or float(
                    data.get("_processing_at") or data.get("_enqueued_at") or 0
                )
                if processing_started_at > 0 and now - processing_started_at > timeout_sec:
                    # Atomically move from processing back to pending
                    removed = self._redis.lrem(proc_key, 0, item)  # type: ignore[attr-defined]
                    if removed:
                        self._redis.lpush(pending_key, item)  # type: ignore[attr-defined]
                        self._ensure_queue_ttl(device_id)  # type: ignore[attr-defined]
                        if state:
                            # AUDIT-9-S4: CAS-protected status update.
                            self._cas_update(  # type: ignore[attr-defined]
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
