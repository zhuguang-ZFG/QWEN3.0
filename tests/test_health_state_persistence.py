"""Tests for health_state.py — persistence functionality."""

import os
import tempfile
import time

os.environ["LIMA_HEALTH_STATE_DB"] = os.path.join(tempfile.gettempdir(), "test_health.db")

import health_state as hs


def test_save_and_load_health_state():
    hs.reset_all_state()
    hs._health_map["test_backend"] = "healthy"
    hs._health_map["bad_backend"] = "dead"
    state = hs.CooldownState(consecutive_failures=3, cooldown_until=time.time() + 60)
    hs._cooldown_states["bad_backend"] = state

    hs.save_health_state()
    hs.reset_all_state()

    loaded = hs.load_health_state()
    assert loaded >= 2
    assert hs._health_map.get("test_backend") == "healthy"
    assert hs._health_map.get("bad_backend") == "dead"
    assert hs._cooldown_states["bad_backend"].consecutive_failures == 3


def test_save_and_load_quality_state():
    hs.reset_all_state()
    quality = hs.QualityState()
    quality.latencies.extend([100, 200, 300])
    quality.empty_count = 5
    quality.total_requests = 10
    hs._quality_states["test_q"] = quality

    hs.save_health_state()
    hs.reset_all_state()

    loaded = hs.load_health_state()
    assert loaded >= 1
    q = hs._quality_states.get("test_q")
    assert q is not None
    assert q.empty_count == 5
    assert q.total_requests == 10
    assert list(q.latencies) == [100, 200, 300]
