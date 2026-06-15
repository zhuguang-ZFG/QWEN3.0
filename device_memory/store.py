"""Memory store with TTL, isolation, and parent controls.

NOTE: The default MemoryStore is in-process only. For multi-worker or
multi-node deployments, replace it with a Redis/SQLite-backed implementation
that shares state across processes. See device_gateway/store.py for the
environment-switch pattern (LIMA_DEVICE_TASK_STORE).
"""
import json
import threading
import time
from typing import List, Optional

from device_memory.schemas import MemoryEntry, MemoryType


class MemoryStore:
    """In-memory store for device memories (testing/dev single-process only)."""

    def __init__(self):
        self._memories: dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()

    def create(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns entry ID."""
        with self._lock:
            self._memories[entry.id] = entry
            return entry.id

    def recall(self, device_id: str, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryEntry]:
        """Recall a memory by device_id and key, respecting TTL and disabled flag."""
        now = int(time.time())
        with self._lock:
            for entry in self._memories.values():
                if entry.device_id != device_id or entry.key != key:
                    continue
                if memory_type and entry.type != memory_type:
                    continue
                if entry.disabled:
                    continue
                # Check TTL
                age_days = (now - entry.created_at) / 86400
                if age_days > entry.ttl_days:
                    continue
                return entry
            return None

    def list_by_device(self, device_id: str, include_expired: bool = False) -> List[MemoryEntry]:
        """List all memories for a device."""
        now = int(time.time())
        with self._lock:
            result = []
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
        """Delete a memory entry. Returns True if deleted."""
        with self._lock:
            if entry_id in self._memories:
                del self._memories[entry_id]
                return True
            return False

    def disable(self, entry_id: str) -> bool:
        """Disable a memory entry (parent control). Returns True if disabled."""
        with self._lock:
            if entry_id in self._memories:
                self._memories[entry_id].disabled = True
                return True
            return False

    def export(self, device_id: str) -> str:
        """Export all memories for a device as JSON."""
        entries = self.list_by_device(device_id, include_expired=True)
        return json.dumps([e.model_dump() for e in entries], indent=2)

    def reset(self, device_id: str) -> int:
        """Delete all memories for a device. Returns count deleted."""
        with self._lock:
            to_delete = [e.id for e in self._memories.values() if e.device_id == device_id]
            for entry_id in to_delete:
                del self._memories[entry_id]
            return len(to_delete)
