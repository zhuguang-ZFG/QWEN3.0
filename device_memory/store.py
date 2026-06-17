"""Memory store backends with env-selectable implementation."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, List, Optional, Protocol

from device_memory.schemas import MemoryEntry, MemoryType


class MemoryStoreBackend(Protocol):
    backend_name: str
    shared_across_processes: bool

    def create(self, entry: MemoryEntry) -> str: ...

    def recall(self, device_id: str, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryEntry]: ...

    def list_by_device(self, device_id: str, include_expired: bool = False) -> List[MemoryEntry]: ...

    def delete(self, entry_id: str) -> bool: ...

    def disable(self, entry_id: str) -> bool: ...

    def export(self, device_id: str) -> str: ...

    def reset(self, device_id: str) -> int: ...


class InMemoryMemoryStore:
    """In-memory store for device memories (default single-process backend)."""

    backend_name = "memory"
    shared_across_processes = False

    def __init__(self) -> None:
        self._memories: dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()

    def create(self, entry: MemoryEntry) -> str:
        with self._lock:
            self._memories[entry.id] = entry
            return entry.id

    def recall(self, device_id: str, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryEntry]:
        now = int(time.time())
        with self._lock:
            for entry in self._memories.values():
                if entry.device_id != device_id or entry.key != key:
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
        with self._lock:
            result: list[MemoryEntry] = []
            for entry in self._memories.values():
                if entry.device_id != device_id:
                    continue
                if not include_expired:
                    age_days = (now - entry.created_at) / 86400
                    if age_days > entry.ttl_days:
                        continue
                result.append(entry)
            return result

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            if entry_id in self._memories:
                del self._memories[entry_id]
                return True
            return False

    def disable(self, entry_id: str) -> bool:
        with self._lock:
            if entry_id in self._memories:
                self._memories[entry_id].disabled = True
                return True
            return False

    def export(self, device_id: str) -> str:
        entries = self.list_by_device(device_id, include_expired=True)
        return json.dumps([e.model_dump() for e in entries], indent=2)

    def reset(self, device_id: str) -> int:
        with self._lock:
            to_delete = [e.id for e in self._memories.values() if e.device_id == device_id]
            for entry_id in to_delete:
                del self._memories[entry_id]
            return len(to_delete)


# Backward-compatible name used in tests and route type hints.
MemoryStore = InMemoryMemoryStore

memory_store: MemoryStoreBackend = InMemoryMemoryStore()


def memory_store_health() -> dict[str, Any]:
    return {
        "backend": getattr(memory_store, "backend_name", memory_store.__class__.__name__),
        "shared_across_processes": bool(getattr(memory_store, "shared_across_processes", False)),
    }


def get_memory_store() -> MemoryStoreBackend:
    return memory_store


def set_memory_store_for_tests(store: MemoryStoreBackend) -> None:
    global memory_store
    memory_store = store


def inject_memory_store(store: MemoryStoreBackend) -> None:
    """Alias for route-level test injection."""
    set_memory_store_for_tests(store)


def configure_memory_store_from_env() -> None:
    global memory_store
    backend = os.environ.get("LIMA_DEVICE_MEMORY_STORE", "").strip().lower()
    redis_url = os.environ.get("LIMA_DEVICE_REDIS_URL", "").strip()
    if backend == "redis":
        if not redis_url:
            raise RuntimeError("LIMA_DEVICE_REDIS_URL is required when LIMA_DEVICE_MEMORY_STORE=redis")
        from device_memory.redis_store import RedisMemoryStore

        memory_store = RedisMemoryStore(redis_url)
    else:
        memory_store = InMemoryMemoryStore()
