"""Memory store backends with env-selectable implementation."""

from __future__ import annotations

import json
import time
from typing import Any, List, Optional, Protocol

from device_gateway.store_utils import StoreConfigMixin, StoreManager
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


class InMemoryMemoryStore(StoreConfigMixin):
    """In-memory store for device memories (default single-process backend)."""

    backend_name = "memory"
    shared_across_processes = False

    def __init__(self) -> None:
        super().__init__()
        self._memories: dict[str, MemoryEntry] = {}

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

memory_manager: StoreManager[MemoryStoreBackend] = StoreManager[MemoryStoreBackend](InMemoryMemoryStore)
memory_store: MemoryStoreBackend = memory_manager.store


def memory_store_health() -> dict[str, Any]:
    return memory_manager.health()


def get_memory_store() -> MemoryStoreBackend:
    return memory_store


def set_memory_store_for_tests(store: MemoryStoreBackend) -> None:
    global memory_store
    memory_manager.set(store)
    memory_store = memory_manager.store


def inject_memory_store(store: MemoryStoreBackend) -> None:
    """Alias for route-level test injection."""
    set_memory_store_for_tests(store)


def configure_memory_store_from_env() -> None:
    global memory_store
    from config.db_config import DEVICE_REDIS_URL

    from device_memory.redis_store import RedisMemoryStore

    memory_manager.configure_from_env(
        "LIMA_DEVICE_MEMORY_STORE",
        DEVICE_REDIS_URL,
        RedisMemoryStore,
    )
    memory_store = memory_manager.store
