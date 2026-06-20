"""Redis-backed append-only device ledger store."""

from __future__ import annotations

import json
import logging
from typing import Any

from device_ledger.events import DuplicateLedgerEvent, LedgerEvent
from device_ledger.store import _replay_from_events

_log = logging.getLogger(__name__)


class RedisLedgerStore:
    backend_name = "redis"
    shared_across_processes = True

    def __init__(self, redis_url: str, *, client: Any | None = None, key_prefix: str = "lima:ledger") -> None:
        if client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("redis package is required for Redis device ledger store") from exc
            client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._redis = client
        self._prefix = key_prefix.rstrip(":")

    def reset(self) -> None:
        keys = list(self._redis.scan_iter(f"{self._prefix}:*"))
        if keys:
            self._redis.delete(*keys)

    def append_event(self, event: LedgerEvent) -> None:
        added = int(self._redis.sadd(self._event_ids_key(), event.event_id))
        if added == 0:
            raise DuplicateLedgerEvent(f"duplicate ledger event id: {event.event_id}")
        encoded = json.dumps(event.to_dict())
        self._redis.rpush(self._task_key(event.task_id), encoded)
        self._redis.rpush(self._device_key(event.device_id), encoded)

    def events_for_task(self, task_id: str) -> list[LedgerEvent]:
        return self._events_from_key(self._task_key(task_id), context=f"task_id={task_id}")

    def events_for_device(self, device_id: str) -> list[LedgerEvent]:
        return self._events_from_key(self._device_key(device_id), context=f"device_id={device_id}")

    def _events_from_key(self, key: str, context: str) -> list[LedgerEvent]:
        raw_events = self._redis.lrange(key, 0, -1) or []
        events: list[LedgerEvent] = []
        for raw in raw_events:
            try:
                data = json.loads(raw)
                events.append(
                    LedgerEvent(
                        event_id=data["event_id"],
                        event_type=data["event_type"],
                        task_id=data["task_id"],
                        device_id=data["device_id"],
                        payload=data.get("payload", {}),
                        created_at=data.get("created_at", ""),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                _log.warning("redis ledger decode failed %s: %s", context, type(exc).__name__)
        return events

    def replay_task(self, task_id: str) -> dict[str, Any]:
        return _replay_from_events(self.events_for_task(task_id), task_id)

    def _event_ids_key(self) -> str:
        return f"{self._prefix}:event_ids"

    def _task_key(self, task_id: str) -> str:
        return f"{self._prefix}:task:{task_id}"

    def _device_key(self, device_id: str) -> str:
        return f"{self._prefix}:device:{device_id}"
