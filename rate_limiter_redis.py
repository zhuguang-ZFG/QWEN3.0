"""Redis-backed keyed rate limits (cross-worker device auth L2)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

_log = logging.getLogger(__name__)

_KEY_PREFIX = "lima:keyed_rate:"
_test_client: Any | None = None
_client: Any | None = None
_client_failed = False


def _auth_rate_redis_flag() -> str:
    return os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS", "auto").strip().lower()


def _redis_url() -> str:
    return (
        os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS_URL", "").strip()
        or os.environ.get("LIMA_DEVICE_REDIS_URL", "").strip()
    )


def use_redis_backend() -> bool:
    flag = _auth_rate_redis_flag()
    if flag in {"0", "false", "memory", "off", "no"}:
        return False
    if flag in {"1", "true", "redis", "on", "yes"}:
        return bool(_redis_url())
    return bool(_redis_url())


def set_test_client(client: Any | None) -> None:
    """Inject a fake Redis client in unit tests."""
    global _test_client, _client, _client_failed
    _test_client = client
    _client = None
    _client_failed = False


def _get_client() -> Any | None:
    global _client, _client_failed
    if _test_client is not None:
        return _test_client
    if _client_failed:
        return None
    if _client is not None:
        return _client
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        _client = redis.Redis.from_url(url, decode_responses=True)
        _client.ping()
    except Exception as exc:
        _client_failed = True
        _log.warning("keyed rate limit Redis unavailable: %s", type(exc).__name__)
        return None
    return _client


def check_keyed(key: str, *, max_per_window: int, window: float) -> bool | None:
    """Return True/False when Redis handled the key; None when Redis is not used."""
    if not use_redis_backend():
        return None
    client = _get_client()
    if client is None:
        return None
    now = time.time()
    limit = max(1, max_per_window)
    bucket = int(now // window)
    rkey = f"{_KEY_PREFIX}{key}:{bucket}"
    try:
        count = int(client.incr(rkey))
        if count == 1:
            client.expire(rkey, int(window) + 1)
        return count <= limit
    except Exception as exc:
        _log.warning("keyed rate limit Redis check failed: %s", type(exc).__name__)
        return None


def reset() -> None:
    client = _test_client if _test_client is not None else _client
    if client is None:
        return
    try:
        for raw in client.scan_iter(f"{_KEY_PREFIX}*"):
            client.delete(raw)
    except Exception as exc:
        _log.warning("keyed rate limit Redis reset failed: %s", type(exc).__name__)
