"""Tests for IP rate-limit Redis backend."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import rate_limiter as rl


class FakeRedisClient:
    """In-memory fake Redis client for testing."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self._expires: dict[str, float] = {}
        self._fail = False

    def set_fail(self, fail: bool) -> None:
        self._fail = fail

    def incr(self, key: str) -> int:
        if self._fail:
            raise ConnectionError("fake Redis failure")
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    def expire(self, key: str, ttl: int) -> None:
        if self._fail:
            raise ConnectionError("fake Redis failure")
        self._expires[key] = time.time() + ttl

    def scan_iter(self, pattern: str) -> list[str]:
        # Simple glob matching
        import fnmatch

        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expires.pop(key, None)


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Reset rate limiter state before each test."""
    rl.reset()
    rl.set_test_client(None)
    rl._redis_client = None
    rl._redis_client_failed = False
    yield
    rl.reset()
    rl.set_test_client(None)
    rl._redis_client = None
    rl._redis_client_failed = False


def test_redis_normal_ip_rate_limit() -> None:
    """Redis handles IP rate limit when enabled."""
    fake = FakeRedisClient()
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        # First request should pass
        assert rl.check_rate_limit("192.168.1.1") is True
        # Check Redis was used
        assert len(fake._store) > 0


def test_redis_normal_ip_exceeds_limit() -> None:
    """Redis returns False when IP exceeds limit."""
    fake = FakeRedisClient()
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        # Simulate hitting limit
        ip = "10.0.0.1"
        max_per_window = rl.MAX_PER_WINDOW
        bucket = int(time.time() // rl.WINDOW)
        rkey = f"lima:ip_rate:{ip}:{bucket}"
        fake._store[rkey] = max_per_window + 1

        assert rl.check_rate_limit(ip) is False


def test_redis_fallback_on_exception() -> None:
    """Redis exception falls back to in-memory with warning."""
    fake = FakeRedisClient()
    fake.set_fail(True)
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        with patch.object(rl._log, "warning") as mock_warn:
            # Should fall back to in-memory
            assert rl.check_rate_limit("172.16.0.1") is True
            # Warning should be logged
            mock_warn.assert_called()
            assert "IP rate-limit Redis fallback" in mock_warn.call_args[0][0]


def test_switch_off_uses_in_memory() -> None:
    """Switch off means in-memory path, no Redis touch."""
    fake = FakeRedisClient()
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "0"}):
        # Should use in-memory, Redis store should be empty
        assert rl.check_rate_limit("192.168.2.2") is True
        assert len(fake._store) == 0


def test_multiplier_effect() -> None:
    """Multiplier affects limit in Redis path."""
    fake = FakeRedisClient()
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        ip = "10.1.1.1"
        multiplier = 2
        max_per_window = rl.MAX_PER_WINDOW * multiplier
        bucket = int(time.time() // rl.WINDOW)
        rkey = f"lima:ip_rate:{ip}:{bucket}"

        # Fill up to one below limit
        fake._store[rkey] = max_per_window - 1
        # Next request should pass (incr to max_per_window)
        assert rl.check_rate_limit(ip, multiplier=multiplier) is True

        # Now at limit, next should exceed
        fake._store[rkey] = max_per_window
        assert rl.check_rate_limit(ip, multiplier=multiplier) is False


def test_ip_rate_redis_flag_from_settings() -> None:
    """_ip_rate_redis_flag reads from settings if available."""
    with patch.object(rl.settings, "SECURITY", create=True) as mock_sec:
        mock_sec.ip_rate_redis = "1"
        assert rl._ip_rate_redis_flag() == "1"

    with patch.object(rl.settings, "SECURITY", create=True) as mock_sec:
        mock_sec.ip_rate_redis = "off"
        assert rl._ip_rate_redis_flag() == "off"


def test_ip_rate_redis_flag_from_env() -> None:
    """_ip_rate_redis_flag falls back to env when settings lacks attribute."""
    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        # settings.SECURITY doesn't have ip_rate_redis
        assert rl._ip_rate_redis_flag() == "1"

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "0"}):
        assert rl._ip_rate_redis_flag() == "0"


def test_ip_check_returns_none_when_disabled() -> None:
    """_check_ip_redis returns None when flag is off."""
    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "0"}):
        assert rl._check_ip_redis("1.2.3.4", max_per_window=100, window=60) is None


def test_ip_check_returns_none_when_no_client() -> None:
    """_check_ip_redis returns None when Redis client unavailable."""
    rl.set_test_client(None)
    rl._redis_client_failed = True
    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        assert rl._check_ip_redis("1.2.3.4", max_per_window=100, window=60) is None


def test_in_memory_fallback_still_works() -> None:
    """In-memory path still functions after Redis failure."""
    fake = FakeRedisClient()
    fake.set_fail(True)
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        # Should fall back to in-memory
        ip = "192.168.3.3"
        # First request
        assert rl.check_rate_limit(ip) is True
        # Multiple requests should still work via in-memory
        for _ in range(rl.MAX_PER_WINDOW - 1):
            assert rl.check_rate_limit(ip) is True
        # Next should be limited
        assert rl.check_rate_limit(ip) is False


def test_redis_key_format() -> None:
    """Redis key follows expected format."""
    fake = FakeRedisClient()
    rl.set_test_client(fake)

    with patch.dict("os.environ", {"LIMA_IP_RATE_REDIS": "1"}):
        ip = "10.20.30.40"
        rl.check_rate_limit(ip)
        bucket = int(time.time() // rl.WINDOW)
        expected_key = f"lima:ip_rate:{ip}:{bucket}"
        assert expected_key in fake._store
