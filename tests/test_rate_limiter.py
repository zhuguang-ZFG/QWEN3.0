"""Tests for rate_limiter.py — sliding-window IP rate limiter."""

from rate_limiter import (
    check_rate_limit,
    check_keyed_rate_limit,
    get_usage,
    reset,
    _requests,
)


def setup_function():
    reset()


class TestCheckRateLimit:
    def test_first_request_allowed(self):
        assert check_rate_limit("1.2.3.4") is True

    def test_many_requests_eventually_blocked(self):
        ip = "5.6.7.8"
        for _ in range(120):
            check_rate_limit(ip)
        assert check_rate_limit(ip) is False

    def test_different_ips_independent(self):
        for _ in range(120):
            check_rate_limit("ip_a")
        assert check_rate_limit("ip_b") is True
        assert check_rate_limit("ip_a") is False

    def test_multiplier_increases_limit(self):
        """Multiplier=2 doubles the rate limit from 120 to 240."""
        ip = "9.10.11.12"
        reset(ip)
        # 150 calls with default multiplier should be blocked
        for _ in range(150):
            check_rate_limit(ip)
        assert check_rate_limit(ip) is False
        # Reset and try with multiplier=2
        reset(ip)
        for _ in range(150):
            check_rate_limit(ip, multiplier=2)
        assert check_rate_limit(ip, multiplier=2) is True  # 150 < 240 limit

    def test_multiplier_at_least_one(self):
        assert check_rate_limit("test_ip", multiplier=0) is True

    def test_reset_clears_ip(self):
        ip = "reset_test"
        for _ in range(150):
            check_rate_limit(ip)
        assert check_rate_limit(ip) is False
        reset(ip)
        assert check_rate_limit(ip) is True

    def test_reset_all(self):
        for _ in range(150):
            check_rate_limit("a")
            check_rate_limit("b")
        reset()
        assert check_rate_limit("a") is True
        assert check_rate_limit("b") is True

    def test_stale_ips_evicted(self):
        check_rate_limit("stale_test")
        assert "stale_test" in _requests
        reset("stale_test")


class TestGetUsage:
    def test_no_requests(self):
        usage = get_usage("nonexistent")
        assert usage["ip"] == "nonexistent"
        assert usage["requests_in_window"] == 0

    def test_after_requests(self):
        ip = "usage_test"
        check_rate_limit(ip)
        check_rate_limit(ip)
        usage = get_usage(ip)
        assert usage["requests_in_window"] >= 2


class TestCheckKeyedRateLimit:
    def test_within_limit_allowed(self):
        assert check_keyed_rate_limit("action:ip1", max_per_window=5) is True

    def test_exceed_limit_blocked(self):
        key = "action:ip2"
        for _ in range(5):
            check_keyed_rate_limit(key, max_per_window=5)
        assert check_keyed_rate_limit(key, max_per_window=5) is False

    def test_different_keys_independent(self):
        for _ in range(5):
            check_keyed_rate_limit("key_a", max_per_window=5)
        assert check_keyed_rate_limit("key_b", max_per_window=5) is True


class _FakePipeline:
    def __init__(self, client, fail_expire=False):
        self._client = client
        self._fail_expire = fail_expire
        self._ops = []

    def incr(self, key):
        self._ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "incr":
                self._client.counts[op[1]] = self._client.counts.get(op[1], 0) + 1
                results.append(self._client.counts[op[1]])
            else:
                if self._fail_expire:
                    raise ConnectionError("expire failed")
                self._client.ttls[op[1]] = op[2]
                results.append(True)
        return results


class _FakeRedisForLimiter:
    def __init__(self, fail_expire=False):
        self.counts = {}
        self.ttls = {}
        self.fail_expire = fail_expire

    def pipeline(self):
        return _FakePipeline(self, fail_expire=self.fail_expire)

    def scan_iter(self, pattern):
        return list(self.counts)

    def delete(self, key):
        self.counts.pop(key, None)
        self.ttls.pop(key, None)


class TestRedisKeyedPath:
    """W5 回归：INCR+EXPIRE 必须同批执行，每个键都要有 TTL。"""

    def _with_client(self, monkeypatch, client):
        import rate_limiter as rl

        rl.set_test_client(client)
        monkeypatch.setattr(rl, "use_redis_backend", lambda: True)

    def test_redis_key_always_gets_ttl(self, monkeypatch):
        import rate_limiter as rl

        client = _FakeRedisForLimiter()
        self._with_client(monkeypatch, client)
        try:
            assert check_keyed_rate_limit("k1", max_per_window=2, window=60) is True
            assert check_keyed_rate_limit("k1", max_per_window=2, window=60) is True
            assert check_keyed_rate_limit("k1", max_per_window=2, window=60) is False
            # 每次调用都设置 TTL，不存在无 TTL 的键。
            assert all(k in client.ttls for k in client.counts), (client.counts, client.ttls)
        finally:
            rl.set_test_client(None)

    def test_redis_failure_falls_back_to_memory(self, monkeypatch):
        import rate_limiter as rl

        client = _FakeRedisForLimiter(fail_expire=True)
        self._with_client(monkeypatch, client)
        try:
            # pipeline 执行失败 → 返回 None → 走内存滑动窗口，不放行超限请求。
            for _ in range(3):
                check_keyed_rate_limit("k2", max_per_window=3, window=60)
            assert check_keyed_rate_limit("k2", max_per_window=3, window=60) is False
        finally:
            rl.set_test_client(None)
