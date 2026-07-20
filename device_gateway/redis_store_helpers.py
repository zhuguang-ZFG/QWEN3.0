"""Private helpers for Redis-backed Device Gateway task store."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from typing import Any

from config.settings import DEVICE

_log = logging.getLogger(__name__)


def connect_redis(
    redis_url: str,
    label: str,
    *,
    client: Any | None = None,
    key_prefix: str = "lima",
) -> tuple[Any, str]:
    """Create or validate a Redis client. Returns (client, prefix).

    Ponytail: three stores each started with this same try/import/from_url
    pattern. Extracted here — upgrade to a connection pool when Redis
    throughput becomes a bottleneck.
    """
    if client is None:
        try:
            import redis as _redis_mod
        except ImportError as exc:
            raise RuntimeError(f"redis package required for {label}") from exc
        # P1 #3（隐藏问题审查）：必须设 socket_timeout，否则 Redis 慢响应/断连会
        # 无限阻塞事件循环（redis-py 默认 socket_timeout=None）。配合同步调用经
        # to_thread 的修复，确保单次 Redis 故障不拖垮全站。
        client = _redis_mod.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return client, key_prefix.rstrip(":")


def encode_redis_json(value: dict[str, Any]) -> str:
    """Serialize a dict to a compact JSON string for Redis storage."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def decode_redis_json(value: str | bytes) -> dict[str, Any]:
    """Deserialize a Redis JSON value, rejecting non-dict payloads."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    data = json.loads(value)
    if not isinstance(data, dict):
        raise RuntimeError(f"expected Redis JSON object, got: {data!r}")
    return data


# SEC-06: strict capability allowlist for tasks popped off the Redis queue.
# A task RPUSHed directly into Redis (bypassing HTTP validation) must still be
# gated before it is forwarded to firmware. Mirrors the HTTP-layer allowlist in
# ``routes/device_app_tasks.py::APP_TASK_CAPABILITIES``.
_ALLOWED_TASK_CAPABILITIES = frozenset(
    {
        "run_path",
        "write_text",
        "draw_generated",
        "draw_image",
        "draw_from_image",
        "handwriting",
        "home",
        "move_abs",
        "move_rel",
        "pause",
        "resume",
        "stop",
        "estop",
        "get_device_info",
    }
)


def validate_task_schema(task: dict[str, Any]) -> bool:
    """SEC-06: return True if a popped task is safe to forward to firmware.

    Rejects tasks whose capability is not on the allowlist, or that are
    missing the ``task_id`` / ``device_id`` fields needed to track and route
    them. This is the last gate before a Redis-sourced task reaches a device.
    """
    if not isinstance(task, dict):
        return False
    if task.get("capability") not in _ALLOWED_TASK_CAPABILITIES:
        return False
    if not task.get("task_id") or not task.get("device_id"):
        return False
    return True


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
        if results:
            self._redis.expire(src, DEVICE.redis_task_ttl)
            self._redis.expire(dst, DEVICE.redis_task_ttl)
        return results

    def _ensure_queue_ttl(self, device_id: str) -> None:
        """Set TTL on pending/processing queues for a device."""
        self._redis.expire(self._queue_key(device_id), DEVICE.redis_task_ttl)
        self._redis.expire(self._processing_key(device_id), DEVICE.redis_task_ttl)

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

    def _index_key(self, device_id: str) -> str:
        return self._key(f"task_idx:{device_id}")

    def _task_index_enabled(self) -> bool:
        return os.environ.get("LIMA_REDIS_TASK_INDEX", "0").strip().lower() in {"1", "true", "on", "yes"}

    def _index_add(self, device_id: str, task_id: str) -> None:
        if not self._task_index_enabled():
            return
        try:
            self._redis.sadd(self._index_key(device_id), task_id)
            self._redis.expire(self._index_key(device_id), DEVICE.redis_task_ttl)
        except Exception as exc:
            _log.warning("task index add failed device=%s task=%s: %s", device_id, task_id, type(exc).__name__)

    def _read_task_state(self, task_id: str) -> dict[str, Any] | None:
        raw = self._redis.hget(self._key("tasks"), task_id)
        if raw is None:
            return None
        return decode_redis_json(raw)

    def _write_task_state(
        self,
        task_id: str,
        state: dict[str, Any],
        expected_version: int | None = None,
    ) -> bool:
        """Write task state.

        AUDIT-9-S4: when ``expected_version`` is not None, use a Lua CAS script
        that only writes if the stored ``_version`` matches; returns True on
        success, False on conflict. When ``expected_version`` is None (default),
        performs a blind overwrite for backward compatibility.
        """
        tasks_key = self._key("tasks")
        ttl = DEVICE.redis_task_ttl
        if expected_version is None:
            self._redis.hset(tasks_key, task_id, encode_redis_json(state))
            self._redis.expire(tasks_key, ttl)
            task_data = state.get("task")
            device_id = task_data.get("device_id") if isinstance(task_data, dict) else None
            if device_id:
                self._index_add(device_id, task_id)
            return True
        # Lazy import to avoid circular dependency at module load.
        from device_gateway.redis_cas import cas_write_state

        success = cas_write_state(self._redis, tasks_key, task_id, state, expected_version, ttl)
        if success:
            task_data = state.get("task")
            device_id = task_data.get("device_id") if isinstance(task_data, dict) else None
            if device_id:
                self._index_add(device_id, task_id)
        return success

    def _cas_update(
        self,
        task_id: str,
        mutator,
        default_state: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        """AUDIT-9-S4: read-modify-write with optimistic CAS + bounded retry.

        Reads current state (or ``default_state`` if missing), applies
        ``mutator(state) -> state`` (in-place), then writes via CAS. On version
        conflict, re-reads and retries up to ``max_retries`` times. Returns the
        final state, or None if the task is missing and no default was provided.
        """
        from device_gateway.redis_cas import bump_version, get_version

        for _ in range(max_retries):
            state = self._read_task_state(task_id)
            if state is None:
                if default_state is None:
                    return None
                state = deepcopy(default_state)
            expected = get_version(state)
            mutator(state)
            bump_version(state)
            if self._write_task_state(task_id, state, expected_version=expected):
                return state
            # Conflict: another writer updated the version; retry.
        _log.warning("cas_update exhausted retries for task=%s", task_id)
        return None


# Include queue/dispatch pipeline so busy checks and status WS "working" see
# tasks that occupy the device before a motion phase is reported.
_ACTIVE_STATUSES = frozenset({"queued", "dispatching", "dispatched", "running", "processing", "progress", "accepted"})

# GW-WG: the self-hosted delivery channel is retired, so queued tasks may never
# be popped; without an age limit they hold the device "busy" forever. Queued
# tasks older than this are lazily expired by expire_stale_queued().
QUEUED_MAX_AGE_SEC = 3600.0
