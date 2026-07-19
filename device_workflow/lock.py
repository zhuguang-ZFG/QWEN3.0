"""Per-task locking backends for WorkflowOrchestrator.

``ThreadTaskLock`` protects concurrent advances within a single process.
``RedisTaskLock`` protects concurrent advances across multiple workers using
Redis SET NX + Lua-delete-only-if-owner.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Protocol

_log = logging.getLogger(__name__)


class TaskLock(Protocol):
    """Acquire and release a lock scoped to a single task_id."""

    def acquire(self, task_id: str) -> bool:
        """Return True if the lock was acquired."""
        ...

    def release(self, task_id: str) -> None:
        """Release the lock. Safe to call even if not currently held."""
        ...


class ThreadTaskLock:
    """In-memory per-task Lock for single-process deployments."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def acquire(self, task_id: str) -> bool:
        with self._lock:
            tlock = self._locks.setdefault(task_id, threading.Lock())
        return tlock.acquire(blocking=False)

    def release(self, task_id: str) -> None:
        with self._lock:
            tlock = self._locks.get(task_id)
        if tlock is not None:
            try:
                tlock.release()
            except RuntimeError:
                _log.warning("thread lock release failed for task %s (not held)", task_id)


class RedisTaskLock:
    """Redis-backed per-task lock for multi-process/multi-worker deployments."""

    def __init__(self, redis_client: Any, *, key_prefix: str = "lima:workflow", ttl_seconds: int = 5) -> None:
        self._redis = redis_client
        self._prefix = key_prefix.rstrip(":")
        self._ttl = ttl_seconds
        self._nonces: dict[str, str] = {}
        self._release_script = self._redis.register_script(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) "
            "else return 0 end"
        )

    def _key(self, task_id: str) -> str:
        return f"{self._prefix}:lock:{task_id}"

    def acquire(self, task_id: str) -> bool:
        nonce = uuid.uuid4().hex
        acquired = bool(
            self._redis.set(self._key(task_id), nonce, nx=True, ex=self._ttl)
        )
        if acquired:
            self._nonces[task_id] = nonce
        return acquired

    def release(self, task_id: str) -> None:
        nonce = self._nonces.pop(task_id, None)
        if nonce is None:
            return
        try:
            self._release_script(keys=[self._key(task_id)], args=[nonce])
        except Exception:
            _log.warning("redis lock release failed for task %s", task_id, exc_info=True)
