"""Simple in-process sliding-window rate limiter (stdlib only, no external deps).

Single-worker accurate. For multi-worker deployments, swap _Store for a
Redis-backed implementation — the public API (check / is_allowed) stays the same.

Usage::

    from device_logic.rate_limit import RateLimiter

    _register_limiter = RateLimiter(max_calls=5, window_seconds=60)

    # In a route handler:
    if not _register_limiter.is_allowed(account_id):
        return err(429, "Too many requests — try again later", 429)
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque


class RateLimiter:
    """Sliding-window rate limiter keyed by arbitrary string (account_id, IP, …).

    Args:
        max_calls: Maximum number of allowed calls within *window_seconds*.
        window_seconds: Length of the sliding window in seconds.
    """

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._max_calls = max_calls
        self._window = window_seconds
        self._lock = threading.Lock()
        # key → deque of call timestamps (oldest first)
        self._calls: dict[str, Deque[float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, key: str) -> bool:
        """Return True and record the call if it is within the rate limit.

        Return False (without recording) if the limit would be exceeded.
        Thread-safe; O(calls_in_window) per invocation.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._calls.setdefault(key, deque())
            # Evict timestamps outside the window
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self._max_calls:
                return False
            dq.append(now)
            return True

    def check(self, key: str) -> None:
        """Like ``is_allowed`` but raises ``RateLimitExceeded`` instead of returning False."""
        if not self.is_allowed(key):
            raise RateLimitExceeded(f"Rate limit exceeded: max {self._max_calls} calls per {self._window}s")

    def reset(self, key: str) -> None:
        """Clear the call history for *key* (useful in tests)."""
        with self._lock:
            self._calls.pop(key, None)

    def reset_all(self) -> None:
        """Clear all call histories (useful in tests)."""
        with self._lock:
            self._calls.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def remaining(self, key: str) -> int:
        """Return calls remaining in the current window for *key*."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            dq = self._calls.get(key, deque())
            active = sum(1 for t in dq if t > cutoff)
            return max(0, self._max_calls - active)


class RateLimitExceeded(Exception):
    """Raised by :meth:`RateLimiter.check` when the limit is exceeded."""
