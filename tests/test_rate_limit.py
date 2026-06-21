"""Tests for device_logic.rate_limit.RateLimiter (L2 fix)."""

from __future__ import annotations

import pytest

import device_logic.rate_limit as _rl_mod
from device_logic.rate_limit import RateLimiter, RateLimitExceeded


# ── basic allow / block ────────────────────────────────────────────────────────


def test_allows_calls_within_limit():
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    assert limiter.is_allowed("user-a") is True
    assert limiter.is_allowed("user-a") is True
    assert limiter.is_allowed("user-a") is True


def test_blocks_when_limit_exceeded():
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    for _ in range(3):
        limiter.is_allowed("user-b")
    assert limiter.is_allowed("user-b") is False


def test_different_keys_are_independent():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    assert limiter.is_allowed("key-1") is True
    assert limiter.is_allowed("key-2") is True  # separate key, full quota


def test_check_raises_on_exceed():
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    limiter.check("user-c")
    limiter.check("user-c")
    with pytest.raises(RateLimitExceeded):
        limiter.check("user-c")


# ── remaining / reset ─────────────────────────────────────────────────────────


def test_remaining_decrements_with_calls():
    limiter = RateLimiter(max_calls=5, window_seconds=60)
    assert limiter.remaining("user-d") == 5
    limiter.is_allowed("user-d")
    assert limiter.remaining("user-d") == 4
    limiter.is_allowed("user-d")
    assert limiter.remaining("user-d") == 3


def test_remaining_never_negative():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    limiter.is_allowed("user-e")
    limiter.is_allowed("user-e")  # blocked, not recorded
    assert limiter.remaining("user-e") == 0


def test_reset_clears_history():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    assert limiter.is_allowed("user-f") is True
    assert limiter.is_allowed("user-f") is False
    limiter.reset("user-f")
    assert limiter.is_allowed("user-f") is True


def test_reset_all_clears_all_keys():
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    limiter.is_allowed("x")
    limiter.is_allowed("y")
    limiter.reset_all()
    assert limiter.is_allowed("x") is True
    assert limiter.is_allowed("y") is True


# ── sliding window ────────────────────────────────────────────────────────────


def test_sliding_window_evicts_old_calls(monkeypatch):
    """Calls older than window_seconds must not count against the current window."""
    limiter = RateLimiter(max_calls=2, window_seconds=5)
    base = 1_000.0
    times = iter([base, base + 1.0, base + 5.0, base + 5.1])
    monkeypatch.setattr(_rl_mod.time, "monotonic", lambda: next(times))

    assert limiter.is_allowed("u") is True  # t=1000   → [1000]
    assert limiter.is_allowed("u") is True  # t=1001   → [1000, 1001]
    # t=1005: window is (1000, 1005], so 1000 is evicted → only [1001] active
    assert limiter.is_allowed("u") is True  # t=1005   → [1001, 1005]
    # t=1005.1: window is (1000.1, 1005.1], [1001] still inside → 2 active → blocked
    assert limiter.is_allowed("u") is False  # t=1005.1 → limit hit


# ── constructor validation ────────────────────────────────────────────────────


def test_invalid_max_calls_raises():
    with pytest.raises(ValueError, match="max_calls"):
        RateLimiter(max_calls=0, window_seconds=60)


def test_invalid_window_raises():
    with pytest.raises(ValueError, match="window_seconds"):
        RateLimiter(max_calls=5, window_seconds=0)
