"""Private helpers for Redis-backed Device Gateway task store."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.redis_store_codec import decode_redis_json, encode_redis_json

_log = logging.getLogger(__name__)


class RedisStoreHelpers:
    """Mixin providing low-level Redis key/state/queue helpers."""

    _redis: Any
    _prefix: str

    def _key(self, suffix: str) -> str:
        return f"{self._prefix}:{suffix}"

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
                data = decode_redis_json(item)
            except Exception as exc:
                _log.warning(
                    "_remove_processing_task device=%s: corrupt processing item ignored: %s",
                    device_id,
                    exc,
                )
                continue
            if data.get("task_id") == task_id:
                return bool(self._redis.lrem(key, 1, item))
        return False

    def _read_task_state(self, task_id: str) -> dict[str, Any] | None:
        raw = self._redis.hget(self._key("tasks"), task_id)
        if raw is None:
            return None
        return decode_redis_json(raw)

    def _write_task_state(self, task_id: str, state: dict[str, Any]) -> None:
        self._redis.hset(self._key("tasks"), task_id, encode_redis_json(state))


_ACTIVE_STATUSES = frozenset({"dispatched", "running", "processing", "progress", "accepted"})
