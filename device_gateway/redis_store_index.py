"""Task-index mixin for RedisDeviceTaskStore (切片 D)."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from config.settings import DEVICE
from device_gateway.redis_store_helpers import _ACTIVE_STATUSES, decode_redis_json

_log = logging.getLogger(__name__)


class RedisTaskIndexMixin:
    """Mixin: 提供基于 Redis Set 的任务索引查询与重建方法。"""

    def _active_tasks_indexed(self, device_id: str) -> list[dict[str, Any]]:
        index_key = self._index_key(device_id)
        ids = self._redis.smembers(index_key)
        if not ids:
            _log.warning("task index cold-start fallback device=%s", device_id)
            self.reconcile_device_index(device_id)
            return self._active_tasks_hgetall(device_id)
        tasks_key = self._key("tasks")
        raw_values = self._redis.hmget(tasks_key, list(ids))
        active: list[dict[str, Any]] = []
        for raw in raw_values:
            if raw is None:
                continue
            try:
                state = decode_redis_json(raw)
            except (UnicodeDecodeError, RuntimeError) as exc:
                _log.warning("redis active task decode failed: %s", type(exc).__name__)
                continue
            task = state.get("task")
            if not isinstance(task, dict) or task.get("device_id") != device_id:
                continue
            if state.get("status") in _ACTIVE_STATUSES:
                active.append(deepcopy(task))
        return active

    def _list_tasks_indexed(
        self,
        device_id: str,
        status: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        index_key = self._index_key(device_id)
        ids = self._redis.smembers(index_key)
        if not ids:
            _log.warning("task index cold-start fallback device=%s", device_id)
            self.reconcile_device_index(device_id)
            return self._list_tasks_hgetall(device_id, status, limit)
        tasks_key = self._key("tasks")
        raw_values = self._redis.hmget(tasks_key, list(ids))
        tasks: list[dict[str, Any]] = []
        for raw in raw_values:
            if raw is None:
                continue
            try:
                state = decode_redis_json(raw)
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

    def reconcile_device_index(self, device_id: str) -> int:
        """Rebuild the per-device task index Set from the canonical hash.

        Best-effort: exceptions are logged and return 0.
        """
        try:
            index_key = self._index_key(device_id)
            raw_states = self._redis.hgetall(self._key("tasks"))
            values = raw_states.items() if isinstance(raw_states, dict) else []
            matching_ids: list[str] = []
            for task_id, raw in values:
                try:
                    state = decode_redis_json(raw)
                except Exception as exc:
                    _log.warning("reconcile decode skip device=%s task=%s: %s", device_id, task_id, type(exc).__name__)
                    continue
                task = state.get("task")
                if isinstance(task, dict) and task.get("device_id") == device_id:
                    matching_ids.append(task_id)
            if not matching_ids:
                self._redis.delete(index_key)
                return 0
            self._redis.sadd(index_key, *matching_ids)
            self._redis.expire(index_key, DEVICE.redis_task_ttl)
            return len(matching_ids)
        except Exception as exc:
            _log.warning("reconcile_device_index failed device=%s: %s", device_id, type(exc).__name__)
            return 0
