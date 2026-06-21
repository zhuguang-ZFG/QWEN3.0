import threading

import rate_limiter


def test_rate_limiter_rejects_after_window_limit(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    assert rate_limiter.check_rate_limit("203.0.113.1") is True
    assert rate_limiter.check_rate_limit("203.0.113.1") is True
    assert rate_limiter.check_rate_limit("203.0.113.1") is False


def test_rate_limiter_multiplier_scales_limit(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    for _ in range(10):
        assert rate_limiter.check_rate_limit("203.0.113.2", multiplier=5) is True
    assert rate_limiter.check_rate_limit("203.0.113.2", multiplier=5) is False


def test_rate_limiter_window_expires_old_requests(monkeypatch):
    start = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: start)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    assert rate_limiter.check_rate_limit("203.0.113.3") is True
    assert rate_limiter.check_rate_limit("203.0.113.3") is True
    assert rate_limiter.check_rate_limit("203.0.113.3") is False

    # Advance beyond the window; the two old requests should be pruned.
    monkeypatch.setattr(rate_limiter.time, "time", lambda: start + rate_limiter.WINDOW + 1)
    assert rate_limiter.check_rate_limit("203.0.113.3") is True
    assert rate_limiter.check_rate_limit("203.0.113.3") is True
    assert rate_limiter.check_rate_limit("203.0.113.3") is False


def test_rate_limiter_multiplier_clamped_to_at_least_one(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 2)
    rate_limiter.reset()

    for multiplier in (0, -1, -10):
        rate_limiter.reset("203.0.113.4")
        assert rate_limiter.check_rate_limit("203.0.113.4", multiplier=multiplier) is True
        assert rate_limiter.check_rate_limit("203.0.113.4", multiplier=multiplier) is True
        assert rate_limiter.check_rate_limit("203.0.113.4", multiplier=multiplier) is False


def test_rate_limiter_evicts_stale_ips(monkeypatch):
    start = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: start)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 1)
    monkeypatch.setattr(rate_limiter, "MAX_TRACKED_IPS", 2)
    rate_limiter.reset()

    assert rate_limiter.check_rate_limit("203.0.113.10") is True
    assert rate_limiter.check_rate_limit("203.0.113.11") is True
    monkeypatch.setattr(rate_limiter.time, "time", lambda: start + rate_limiter.WINDOW + 1)
    assert rate_limiter.check_rate_limit("203.0.113.12") is True
    assert len(rate_limiter._requests) <= 2


def test_rate_limiter_is_thread_safe_under_same_ip(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    monkeypatch.setattr(rate_limiter, "MAX_PER_WINDOW", 100)
    rate_limiter.reset()

    allowed = []

    def worker() -> None:
        for _ in range(50):
            if rate_limiter.check_rate_limit("203.0.113.99"):
                allowed.append(1)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(allowed) == 100


def test_keyed_rate_limiter_enforces_per_key_limit(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limiter.time, "time", lambda: now)
    rate_limiter.reset()

    assert rate_limiter.check_keyed_rate_limit("device_auth:register:1.2.3.4", max_per_window=2) is True
    assert rate_limiter.check_keyed_rate_limit("device_auth:register:1.2.3.4", max_per_window=2) is True
    assert rate_limiter.check_keyed_rate_limit("device_auth:register:1.2.3.4", max_per_window=2) is False
    assert rate_limiter.check_keyed_rate_limit("device_auth:register:5.6.7.8", max_per_window=2) is True


class _FakeRateRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttl: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.ttl[key] = seconds
        return True

    def scan_iter(self, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                removed += 1
            self.ttl.pop(key, None)
        return removed


def test_keyed_rate_limit_redis_backend(monkeypatch):
    import rate_limiter_redis as redis_backend

    fake = _FakeRateRedis()
    monkeypatch.setenv("LIMA_DEVICE_AUTH_RATE_REDIS", "1")
    monkeypatch.setenv("LIMA_DEVICE_AUTH_RATE_REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_backend.set_test_client(fake)
    rate_limiter.reset()

    key = "device_auth:login:203.0.113.50"
    assert rate_limiter.check_keyed_rate_limit(key, max_per_window=2) is True
    assert rate_limiter.check_keyed_rate_limit(key, max_per_window=2) is True
    assert rate_limiter.check_keyed_rate_limit(key, max_per_window=2) is False

    redis_backend.set_test_client(None)
    rate_limiter.reset()
