"""Sliding-window IP rate limiter + Redis-backed keyed rate limits."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from config import settings

_log = logging.getLogger(__name__)

WINDOW = 60
MAX_PER_WINDOW = 120
MAX_TRACKED_IPS = 50_000

_lock = threading.Lock()
_requests: dict[str, list[float]] = {}
_keyed_lock = threading.Lock()
_keyed_requests: dict[str, list[float]] = {}

# --- Redis keyed rate limit (cross-worker device auth L2) ---

# --- IP Redis rate limit (cross-worker IP sliding window) ---

_IP_RATE_REDIS_KEY = "LIMA_IP_RATE_REDIS"


def _ip_rate_redis_flag() -> str:
    """Return the IP rate-limit Redis flag from settings or env."""
    # Prefer settings.SECURITY.ip_rate_redis if it exists
    flag = getattr(settings.SECURITY, "ip_rate_redis", None)
    if flag is not None:
        return str(flag).strip().lower()
    # Fallback to environment variable
    return os.environ.get(_IP_RATE_REDIS_KEY, "0").strip().lower()


# --- Redis keyed rate limit (cross-worker device auth L2) ---

_KEY_PREFIX = "lima:keyed_rate:"
_test_client: Any | None = None
_redis_client: Any | None = None
_redis_client_failed = False


def _auth_rate_redis_flag() -> str:
    return settings.SECURITY.device_auth_rate_redis


def _redis_url() -> str:
    from config.db_config import DEVICE_REDIS_URL

    return settings.SECURITY.device_auth_rate_redis_url or DEVICE_REDIS_URL


def use_redis_backend() -> bool:
    flag = _auth_rate_redis_flag()
    if flag in {"0", "false", "memory", "off", "no"}:
        return False
    if flag in {"1", "true", "redis", "on", "yes"}:
        return bool(_redis_url())
    return bool(_redis_url())


def set_test_client(client: Any | None) -> None:
    """Inject a fake Redis client in unit tests."""
    global _test_client, _redis_client, _redis_client_failed
    _test_client = client
    _redis_client = None
    _redis_client_failed = False


def _get_redis_client() -> Any | None:
    global _redis_client, _redis_client_failed
    if _test_client is not None:
        return _test_client
    if _redis_client_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        _redis_client = redis.Redis.from_url(url, decode_responses=True)
        _redis_client.ping()
    except Exception as exc:
        _redis_client_failed = True
        _log.warning("keyed rate limit Redis unavailable: %s", type(exc).__name__)
        return None
    return _redis_client


def _check_keyed_redis(key: str, *, max_per_window: int, window: float) -> bool | None:
    """Return True/False when Redis handled the key; None when Redis is not used."""
    if not use_redis_backend():
        return None
    client = _get_redis_client()
    if client is None:
        return None
    limit = max(1, max_per_window)
    bucket = int(time.time() // window)
    rkey = f"{_KEY_PREFIX}{key}:{bucket}"
    try:
        count = int(client.incr(rkey))
        if count == 1:
            client.expire(rkey, int(window) + 1)
        return count <= limit
    except Exception as exc:
        _log.warning("keyed rate limit Redis check failed: %s", type(exc).__name__)
        return None


def _check_ip_redis(ip: str, *, max_per_window: int, window: float) -> bool | None:
    """Return True/False when Redis handled the IP; None when Redis is not used."""
    if _ip_rate_redis_flag() in {"0", "false", "memory", "off", "no"}:
        return None
    client = _get_redis_client()
    if client is None:
        return None
    limit = max(1, max_per_window)
    bucket = int(time.time() // window)
    rkey = f"lima:ip_rate:{ip}:{bucket}"
    try:
        count = int(client.incr(rkey))
        if count == 1:
            client.expire(rkey, int(window) + 1)
        return count <= limit
    except Exception as exc:
        _log.warning("IP rate-limit Redis fallback: %s", type(exc).__name__)
        return None


def _reset_redis() -> None:
    client = _test_client if _test_client is not None else _redis_client
    if client is None:
        return
    try:
        for raw in client.scan_iter(f"{_KEY_PREFIX}*"):
            client.delete(raw)
    except Exception as exc:
        _log.warning("keyed rate limit Redis reset failed: %s", type(exc).__name__)


# --- In-memory sliding-window IP limiter ---


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
    # Try Redis-backed IP rate limit first if enabled
    redis_result = _check_ip_redis(ip, max_per_window=MAX_PER_WINDOW * max(1, multiplier), window=WINDOW)
    if redis_result is not None:
        return redis_result

    # Fall back to in-memory sliding window
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
    redis_result = _check_keyed_redis(key, max_per_window=max_per_window, window=window)
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
    _reset_redis()
