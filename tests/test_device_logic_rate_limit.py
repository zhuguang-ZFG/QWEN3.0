"""Tests for device_logic.rate_limit."""

from __future__ import annotations

import threading
import time

import pytest

from device_logic.rate_limit import RateLimiter, RateLimitExceeded


class TestRateLimiterConstruction:
    def test_accepts_positive_args(self) -> None:
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        assert limiter._max_calls == 3
        assert limiter._window == 1.0

    def test_rejects_zero_max_calls(self) -> None:
        with pytest.raises(ValueError, match="max_calls must be >= 1"):
            RateLimiter(max_calls=0, window_seconds=1.0)

    def test_rejects_negative_max_calls(self) -> None:
        with pytest.raises(ValueError, match="max_calls must be >= 1"):
            RateLimiter(max_calls=-1, window_seconds=1.0)

    def test_rejects_zero_window(self) -> None:
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(max_calls=1, window_seconds=0.0)

    def test_rejects_negative_window(self) -> None:
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimiter(max_calls=1, window_seconds=-1.0)


class TestRateLimiterIsAllowed:
    def test_allows_up_to_max_calls(self) -> None:
        limiter = RateLimiter(max_calls=2, window_seconds=60.0)
        assert limiter.is_allowed("user_1") is True
        assert limiter.is_allowed("user_1") is True
        assert limiter.is_allowed("user_1") is False

    def test_keys_are_independent(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        assert limiter.is_allowed("user_a") is True
        assert limiter.is_allowed("user_b") is True
        assert limiter.is_allowed("user_a") is False

    def test_sliding_window_evicts_old_calls(self) -> None:
        limiter = RateLimiter(max_calls=2, window_seconds=0.1)
        assert limiter.is_allowed("key") is True
        assert limiter.is_allowed("key") is True
        assert limiter.is_allowed("key") is False
        time.sleep(0.11)
        assert limiter.is_allowed("key") is True


class TestRateLimiterCheck:
    def test_check_passes_when_allowed(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        limiter.check("key")  # should not raise

    def test_check_raises_when_exceeded(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        limiter.check("key")
        with pytest.raises(RateLimitExceeded, match="Rate limit exceeded"):
            limiter.check("key")


class TestRateLimiterReset:
    def test_reset_clears_single_key(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        assert limiter.is_allowed("key") is True
        assert limiter.is_allowed("key") is False
        limiter.reset("key")
        assert limiter.is_allowed("key") is True

    def test_reset_all_clears_all_keys(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        assert limiter.is_allowed("a") is True
        assert limiter.is_allowed("b") is True
        assert limiter.is_allowed("a") is False
        assert limiter.is_allowed("b") is False
        limiter.reset_all()
        assert limiter.is_allowed("a") is True
        assert limiter.is_allowed("b") is True


class TestRateLimiterRemaining:
    def test_remaining_decreases_with_calls(self) -> None:
        limiter = RateLimiter(max_calls=3, window_seconds=60.0)
        assert limiter.remaining("key") == 3
        limiter.is_allowed("key")
        assert limiter.remaining("key") == 2
        limiter.is_allowed("key")
        assert limiter.remaining("key") == 1
        limiter.is_allowed("key")
        assert limiter.remaining("key") == 0

    def test_remaining_does_not_record_calls(self) -> None:
        limiter = RateLimiter(max_calls=1, window_seconds=60.0)
        assert limiter.remaining("key") == 1
        assert limiter.remaining("key") == 1
        assert limiter.is_allowed("key") is True


class TestRateLimiterThreadSafety:
    def test_concurrent_is_allowed_is_safe(self) -> None:
        limiter = RateLimiter(max_calls=1000, window_seconds=60.0)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(100):
                    limiter.is_allowed("shared")
                    limiter.remaining("shared")
            except Exception as exc:  # pragma: no cover - safety net
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All recorded calls should still be within the limit.
        assert limiter.is_allowed("shared") is False
