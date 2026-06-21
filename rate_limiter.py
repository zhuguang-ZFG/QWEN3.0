"""Sliding-window IP rate limiter for chat endpoints."""

from __future__ import annotations

import threading
import time

import rate_limiter_redis

WINDOW = 60
MAX_PER_WINDOW = 120
MAX_TRACKED_IPS = 50_000

_lock = threading.Lock()
_requests: dict[str, list[float]] = {}
_keyed_lock = threading.Lock()
_keyed_requests: dict[str, list[float]] = {}


def _prune_recent(timestamps: list[float], now: float, window: float = WINDOW) -> list[float]:
    return [t for t in timestamps if now - t < window]


def _drop_stale_ips(now: float) -> None:
    stale = [ip for ip, times in _requests.items() if not times or now - times[-1] >= WINDOW]
    for ip in stale:
        del _requests[ip]


def _evict_oldest_ips() -> None:
    if len(_requests) <= MAX_TRACKED_IPS:
        return
    victims = sorted(_requests.items(), key=lambda item: item[1][-1] if item[1] else 0.0)
    count = max(len(_requests) - MAX_TRACKED_IPS, len(_requests) // 4)
    for ip, _ in victims[:count]:
        _requests.pop(ip, None)


def check_rate_limit(ip: str, multiplier: int = 1) -> bool:
    """Return True when the client is within its sliding-window limit."""
    now = time.time()
    limit = max(1, MAX_PER_WINDOW * max(1, multiplier))
    with _lock:
        recent = _prune_recent(_requests.get(ip, []), now)
        if len(recent) >= limit:
            if recent:
                _requests[ip] = recent
            else:
                _requests.pop(ip, None)
            _drop_stale_ips(now)
            return False
        recent.append(now)
        _requests[ip] = recent
        _drop_stale_ips(now)
        if len(_requests) > MAX_TRACKED_IPS:
            _evict_oldest_ips()
    return True


def check_keyed_rate_limit(key: str, *, max_per_window: int, window: float = WINDOW) -> bool:
    """Sliding-window limiter keyed by arbitrary string (e.g. device auth action + IP)."""
    redis_result = rate_limiter_redis.check_keyed(key, max_per_window=max_per_window, window=window)
    if redis_result is not None:
        return redis_result

    now = time.time()
    limit = max(1, max_per_window)
    with _keyed_lock:
        recent = _prune_recent(_keyed_requests.get(key, []), now, window)
        if len(recent) >= limit:
            if recent:
                _keyed_requests[key] = recent
            else:
                _keyed_requests.pop(key, None)
            return False
        recent.append(now)
        _keyed_requests[key] = recent
    return True


def get_usage(ip: str) -> dict:
    """Return current IP usage for debug/admin surfaces."""
    now = time.time()
    with _lock:
        recent = _prune_recent(_requests.get(ip, []), now)
        if recent:
            _requests[ip] = recent
        else:
            _requests.pop(ip, None)
        _drop_stale_ips(now)
    return {"ip": ip, "requests_in_window": len(recent), "limit": MAX_PER_WINDOW}


def reset(ip: str | None = None) -> None:
    """Reset limiter state, mainly for tests."""
    with _lock:
        if ip:
            _requests.pop(ip, None)
        else:
            _requests.clear()
    with _keyed_lock:
        if ip is None:
            _keyed_requests.clear()
    rate_limiter_redis.reset()
