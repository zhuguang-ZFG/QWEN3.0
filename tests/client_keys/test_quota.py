"""Tests for client_keys quota tracker."""

from __future__ import annotations

import time

import pytest

from client_keys.models import ClientKey
from client_keys.quota import QuotaTracker


def _make_key(**overrides) -> ClientKey:
    defaults = {
        "key_id": "ck-test",
        "key_value": "lima-test-token-1234",
        "label": "test",
        "enabled": True,
        "quota_daily": 1000,
        "quota_monthly": 30000,
        "rate_limit_rpm": 20,
    }
    defaults.update(overrides)
    return ClientKey(**defaults)


@pytest.fixture
def tracker(tmp_path):
    return QuotaTracker(str(tmp_path / "quota.db"), rpm_window_seconds=0.5)


def test_unlimited_quota_returns_allowed(tracker):
    key = _make_key(quota_daily=0, quota_monthly=0)
    allowed, reason = tracker.try_consume_quota(key)
    assert allowed is True
    assert reason == ""


def test_daily_limit_enforced(tracker):
    key = _make_key(quota_daily=2)
    assert tracker.try_consume_quota(key)[0] is True
    assert tracker.try_consume_quota(key)[0] is True
    allowed, reason = tracker.try_consume_quota(key)
    assert allowed is False
    assert reason == "daily_limit"


def test_monthly_limit_enforced(tracker):
    key = _make_key(quota_monthly=1)
    assert tracker.try_consume_quota(key)[0] is True
    allowed, reason = tracker.try_consume_quota(key)
    assert allowed is False
    assert reason == "monthly_limit"


def test_rpm_limit_enforced(tracker):
    key = _make_key(rate_limit_rpm=2)
    assert tracker.try_consume_quota(key)[0] is True
    assert tracker.try_consume_quota(key)[0] is True
    allowed, reason = tracker.try_consume_quota(key)
    assert allowed is False
    assert reason == "rpm_limit"


def test_check_quota_disabled_key(tracker):
    key = _make_key(enabled=False)
    assert tracker.check_key_quota(key) is False


def test_usage_summary_tracks_counts(tracker):
    key = _make_key()
    tracker.try_consume_quota(key)
    tracker.try_consume_quota(key)
    summary = tracker.usage_summary(key.key_value)
    assert summary["daily_count"] == 2
    assert summary["monthly_count"] == 2
    assert summary["last_used_at"] is not None


def test_clear_token_resets_usage(tracker):
    key = _make_key()
    tracker.try_consume_quota(key)
    tracker.clear_token(key.key_value)
    summary = tracker.usage_summary(key.key_value)
    assert summary["daily_count"] == 0
    assert summary["monthly_count"] == 0


def test_rpm_window_slides_over_time(tracker):
    key = _make_key(rate_limit_rpm=1)
    assert tracker.try_consume_quota(key)[0] is True
    allowed, reason = tracker.try_consume_quota(key)
    assert allowed is False
    assert reason == "rpm_limit"
    time.sleep(1.05)
    assert tracker.try_consume_quota(key)[0] is True
