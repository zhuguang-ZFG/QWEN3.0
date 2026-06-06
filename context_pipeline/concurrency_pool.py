"""Concurrency-Aware Key Pool — sub2api-inspired concurrent request management.

Upgrades basic SWRR key rotation with:
- Per-key concurrent request tracking
- Automatic rotation when key hits concurrency limit
- 429/rate-limit cooldown with smart rotation
- Quota-aware scheduling
"""

import threading
import time
from dataclasses import dataclass


@dataclass
class KeyState:
    """State for a single API key."""

    key: str
    in_flight: int = 0
    max_concurrent: int = 3
    total_requests: int = 0
    total_failures: int = 0
    cooldown_until: float = 0.0

    @property
    def is_available(self) -> bool:
        return (
            self.in_flight < self.max_concurrent
            and time.time() > self.cooldown_until
        )

    @property
    def is_cooled_down(self) -> bool:
        return time.time() <= self.cooldown_until


class ConcurrencyPool:
    """Concurrency-aware key pool with smart rotation."""

    def __init__(self, keys: list[str], max_concurrent: int = 3) -> None:
        self._lock = threading.Lock()
        self._keys: list[KeyState] = [
            KeyState(key=k, max_concurrent=max_concurrent) for k in keys
        ]
        self._index = 0

    def acquire(self) -> str | None:
        """Acquire an available key. Returns None if all exhausted."""
        with self._lock:
            n = len(self._keys)
            for _ in range(n):
                ks = self._keys[self._index % n]
                self._index += 1
                if ks.is_available:
                    ks.in_flight += 1
                    ks.total_requests += 1
                    return ks.key
            return None

    def release(self, key: str) -> None:
        """Release a key after request completes."""
        with self._lock:
            for ks in self._keys:
                if ks.key == key:
                    ks.in_flight = max(0, ks.in_flight - 1)
                    break

    def mark_rate_limited(self, key: str, cooldown_sec: float = 60.0) -> None:
        """Mark a key as rate-limited (429 received)."""
        with self._lock:
            for ks in self._keys:
                if ks.key == key:
                    ks.cooldown_until = time.time() + cooldown_sec
                    ks.in_flight = max(0, ks.in_flight - 1)
                    ks.total_failures += 1
                    break

    def rotate_on_failure(self, failed_key: str) -> str | None:
        """Rotate to next available key after failure."""
        self.mark_rate_limited(failed_key)
        return self.acquire()

    @property
    def available_count(self) -> int:
        with self._lock:
            return sum(1 for ks in self._keys if ks.is_available)

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def stats(self) -> dict:
        with self._lock:
            return {
                "total_keys": len(self._keys),
                "available": sum(1 for ks in self._keys if ks.is_available),
                "in_flight": sum(ks.in_flight for ks in self._keys),
                "cooled_down": sum(1 for ks in self._keys if ks.is_cooled_down),
            }
