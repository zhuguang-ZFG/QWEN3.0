"""Per-account/device connection limits for device status WebSockets."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_active: dict[tuple[str, str], int] = {}


def try_acquire(account_id: str, device_id: str, *, max_concurrent: int) -> bool:
    key = (account_id, device_id)
    if not all(key):
        return False
    with _lock:
        current = _active.get(key, 0)
        if current >= max(1, max_concurrent):
            return False
        _active[key] = current + 1
        return True


def release(account_id: str, device_id: str) -> None:
    key = (account_id, device_id)
    with _lock:
        current = _active.get(key, 0)
        if current <= 1:
            _active.pop(key, None)
        else:
            _active[key] = current - 1


def count(account_id: str, device_id: str) -> int:
    with _lock:
        return _active.get((account_id, device_id), 0)


def reset() -> None:
    with _lock:
        _active.clear()
