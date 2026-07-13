"""In-memory route memory store for sticky backend routing decisions."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger(__name__)

# Hard cap on route memory entries to prevent unbounded growth.
_MAX_RECORDS = 5_000

# ── Memory store for route decisions ───────────────────────────────────────────

_ROUTE_MEMORY_LOCK = threading.Lock()
_ROUTE_MEMORY: OrderedDict[str, RouteMemoryRecord] = OrderedDict()

# ── Data structures ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RouteMemoryRecord:
    """Per-device route memory for sticky routing decisions."""

    device_id: str
    preferred_backends: list[str]
    last_route_timestamp: str
    success_count: int
    total_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "preferred_backends": self.preferred_backends,
            "last_route_timestamp": self.last_route_timestamp,
            "success_count": self.success_count,
            "total_count": self.total_count,
        }


# ── Public API ────────────────────────────────────────────────────────────────


def _evict_oldest_route() -> None:
    """FIFO-evict oldest entry when route memory exceeds capacity."""
    evicted = False
    while len(_ROUTE_MEMORY) >= _MAX_RECORDS:
        _ROUTE_MEMORY.popitem(last=False)
        evicted = True
    if evicted:
        _log.warning("Route memory exceeded %d records; evicted oldest entries", _MAX_RECORDS)


def record_route_decision(device_id: str, backend: str, success: bool) -> None:
    """Record a routing decision for a device.

    Updates the route memory store to favor successful backends and track
    decision history for sticky routing.
    """
    if not device_id or not backend:
        _log.debug("Skipping route decision with empty device_id or backend")
        return

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    with _ROUTE_MEMORY_LOCK:
        if device_id not in _ROUTE_MEMORY:
            # FIFO eviction before inserting a new key
            _evict_oldest_route()
            _ROUTE_MEMORY[device_id] = RouteMemoryRecord(
                device_id=device_id,
                preferred_backends=[backend],
                last_route_timestamp=now,
                success_count=1 if success else 0,
                total_count=1,
            )
        else:
            record = _ROUTE_MEMORY[device_id]
            updated_backends = [backend] + [b for b in record.preferred_backends if b != backend]

            new_success_count = record.success_count + (1 if success else 0)
            new_total_count = record.total_count + 1

            _ROUTE_MEMORY[device_id] = RouteMemoryRecord(
                device_id=device_id,
                preferred_backends=updated_backends[:10],  # keep top 10
                last_route_timestamp=now,
                success_count=new_success_count,
                total_count=new_total_count,
            )

        _log.debug("Recorded route decision: device=%s, backend=%s, success=%s", device_id, backend, success)


def get_route_memory(device_id: str) -> dict[str, Any]:
    """Get route memory for a device.

    Returns the route memory record, or empty dict if no memory exists.
    """
    with _ROUTE_MEMORY_LOCK:
        record = _ROUTE_MEMORY.get(device_id)
    return record.to_dict() if record else {}


def reset_route_memory_for_tests() -> None:
    """Clear all route memory (test isolation hook)."""
    with _ROUTE_MEMORY_LOCK:
        _ROUTE_MEMORY.clear()
