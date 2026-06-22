"""Redis-backed device memory store."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, List, Optional

from device_memory.schemas import MemoryEntry, MemoryType
from device_gateway.redis_store_codec import connect_redis

_log = logging.getLogger(__name__)

# Default Redis key TTL for device memory indexes (seconds)
_DEFAULT_INDEX_TTL = int(os.environ.get("LIMA_REDIS_MEMORY_INDEX_TTL", "2592000"))  # 30 days


class RedisMemoryStore:
    backend_name = "redis"
    shared_across_processes = True

    def __init__(self, redis_url: str, *, client: Any | None = None, key_prefix: str = "lima:memory") -> None:
        self._redis, self._prefix = connect_redis(redis_url, "RedisMemoryStore", client=client, key_prefix=key_prefix)

    def create(self, entry: MemoryEntry) -> str:
        entry_ttl = max(1, int(entry.ttl_days * 86400))
        self._redis.set(self._entry_key(entry.id), entry.model_dump_json(), ex=entry_ttl)
        device_key = self._device_key(entry.device_id)
        self._redis.sadd(device_key, entry.id)
        self._redis.expire(device_key, _DEFAULT_INDEX_TTL)
        return entry.id

    def recall(self, device_id: str, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryEntry]:
        now = int(time.time())
        for entry in self.list_by_device(device_id, include_expired=False):
            if entry.key != key:
                continue
            if memory_type and entry.type != memory_type:
                continue
            if entry.disabled:
                continue
            age_days = (now - entry.created_at) / 86400
            if age_days > entry.ttl_days:
                continue
            return entry
        return None

    def list_by_device(self, device_id: str, include_expired: bool = False) -> List[MemoryEntry]:
        now = int(time.time())
        entry_ids = self._redis.smembers(self._device_key(device_id)) or []
        result: list[MemoryEntry] = []
        for entry_id in sorted(entry_ids):
            raw = self._redis.get(self._entry_key(entry_id))
            if not raw:
                continue
            try:
                entry = MemoryEntry.model_validate_json(raw)
            except (ValueError, TypeError) as exc:
                _log.warning("redis memory decode failed entry_id=%s: %s", entry_id, type(exc).__name__)
                continue
            if not include_expired:
                age_days = (now - entry.created_at) / 86400
                if age_days > entry.ttl_days:
                    continue
            result.append(entry)
        return result

    def delete(self, entry_id: str) -> bool:
        raw = self._redis.get(self._entry_key(entry_id))
        if not raw:
            return False
        try:
            entry = MemoryEntry.model_validate_json(raw)
        except (ValueError, TypeError):
            self._redis.delete(self._entry_key(entry_id))
            return True
        self._redis.delete(self._entry_key(entry_id))
        self._redis.srem(self._device_key(entry.device_id), entry_id)
        return True

    def disable(self, entry_id: str) -> bool:
        raw = self._redis.get(self._entry_key(entry_id))
        if not raw:
            return False
        entry = MemoryEntry.model_validate_json(raw)
        updated = entry.model_copy(update={"disabled": True})
        entry_ttl = max(1, int(updated.ttl_days * 86400))
        self._redis.set(self._entry_key(entry_id), updated.model_dump_json(), ex=entry_ttl)
        return True

    def export(self, device_id: str) -> str:
        entries = self.list_by_device(device_id, include_expired=True)
        return json.dumps([e.model_dump() for e in entries], indent=2)

    def reset(self, device_id: str) -> int:
        entry_ids = list(self._redis.smembers(self._device_key(device_id)) or [])
        for entry_id in entry_ids:
            self._redis.delete(self._entry_key(entry_id))
        if entry_ids:
            self._redis.delete(self._device_key(device_id))
        return len(entry_ids)

    def _entry_key(self, entry_id: str) -> str:
        return f"{self._prefix}:entry:{entry_id}"

    def _device_key(self, device_id: str) -> str:
        return f"{self._prefix}:device:{device_id}"
