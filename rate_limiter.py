"""Sliding-window IP rate limiter for chat endpoints."""

from __future__ import annotations

import time
from collections import defaultdict

WINDOW = 60
MAX_PER_WINDOW = 120

_requests: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str, multiplier: int = 1) -> bool:
    """Return True when the client is within its sliding-window limit."""
    now = time.time()
    limit = max(1, MAX_PER_WINDOW * max(1, multiplier))
    recent = [t for t in _requests[ip] if now - t < WINDOW]
    if len(recent) >= limit:
        _requests[ip] = recent
        return False
    recent.append(now)
    _requests[ip] = recent
    return True


def get_usage(ip: str) -> dict:
    """Return current IP usage for debug/admin surfaces."""
    now = time.time()
    recent = [t for t in _requests[ip] if now - t < WINDOW]
    return {"ip": ip, "requests_in_window": len(recent), "limit": MAX_PER_WINDOW}


def reset(ip: str | None = None) -> None:
    """Reset limiter state, mainly for tests."""
    if ip:
        _requests.pop(ip, None)
    else:
        _requests.clear()
