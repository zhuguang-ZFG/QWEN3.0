"""Per-account concurrent voice WebSocket connection tracking."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_active: dict[str, int] = {}


def try_acquire(account_id: str, *, max_concurrent: int) -> bool:
    """Reserve a connection slot for *account_id*. Returns False when at capacity."""
    if not account_id:
        return False
    limit = max(1, max_concurrent)
    with _lock:
        current = _active.get(account_id, 0)
        if current >= limit:
            return False
        _active[account_id] = current + 1
        return True


def release(account_id: str) -> None:
    """Release a previously acquired connection slot."""
    if not account_id:
        return
    with _lock:
        current = _active.get(account_id, 0)
        if current <= 1:
            _active.pop(account_id, None)
        else:
            _active[account_id] = current - 1


def count(account_id: str) -> int:
    """Return active connection count for *account_id* (tests/diagnostics)."""
    with _lock:
        return _active.get(account_id, 0)


def reset() -> None:
    """Clear connection counters (tests only)."""
    with _lock:
        _active.clear()
