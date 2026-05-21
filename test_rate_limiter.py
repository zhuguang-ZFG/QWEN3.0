"""
test_rate_limiter.py — 限流模块测试
"""
import time
import rate_limiter


class TestRateLimiter:

    def setup_method(self):
        rate_limiter.reset()

    def test_allows_under_limit(self):
        for _ in range(19):
            assert rate_limiter.check_rate_limit("1.2.3.4") is True

    def test_blocks_at_limit(self):
        for _ in range(20):
            rate_limiter.check_rate_limit("1.2.3.4")
        assert rate_limiter.check_rate_limit("1.2.3.4") is False

    def test_different_ips_independent(self):
        for _ in range(20):
            rate_limiter.check_rate_limit("1.1.1.1")
        assert rate_limiter.check_rate_limit("1.1.1.1") is False
        assert rate_limiter.check_rate_limit("2.2.2.2") is True

    def test_get_usage(self):
        rate_limiter.check_rate_limit("5.5.5.5")
        rate_limiter.check_rate_limit("5.5.5.5")
        usage = rate_limiter.get_usage("5.5.5.5")
        assert usage["requests_in_window"] == 2
        assert usage["limit"] == 20

    def test_reset_clears_state(self):
        for _ in range(20):
            rate_limiter.check_rate_limit("9.9.9.9")
        rate_limiter.reset("9.9.9.9")
        assert rate_limiter.check_rate_limit("9.9.9.9") is True
