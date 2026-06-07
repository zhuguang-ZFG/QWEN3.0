"""Tests for quality_history.py — per-backend quality score persistence."""

import time
from unittest.mock import patch

import quality_history


def setup_function():
    quality_history.reset_all()


# ── Basic recording and retrieval ────────────────────────────────────────────

def test_record_and_get_trend():
    for i in range(10):
        quality_history.record_quality("backend_a", 80.0)
    trend = quality_history.get_quality_trend("backend_a")
    assert trend.average == 80.0
    assert trend.sample_count == 10


def test_get_trend_no_history_returns_defaults():
    trend = quality_history.get_quality_trend("nonexistent")
    assert trend.average == 50.0
    assert trend.trend == "stable"
    assert trend.confidence == 0.0
    assert trend.sample_count == 0


def test_score_clamped_to_range():
    quality_history.record_quality("clamp_test", 150.0)
    quality_history.record_quality("clamp_test", -20.0)
    trend = quality_history.get_quality_trend("clamp_test")
    assert 0.0 <= trend.average <= 100.0


# ── Trend direction detection ────────────────────────────────────────────────

def test_declining_trend_detected():
    # First half: high scores, second half: low scores
    for _ in range(10):
        quality_history.record_quality("declining_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("declining_backend", 30.0)
    trend = quality_history.get_quality_trend("declining_backend")
    assert trend.trend == "declining", f"Expected declining, got {trend.trend}"
    assert trend.confidence > 0.0


def test_improving_trend_detected():
    # First half: low scores, second half: high scores
    for _ in range(10):
        quality_history.record_quality("improving_backend", 30.0)
    for _ in range(10):
        quality_history.record_quality("improving_backend", 90.0)
    trend = quality_history.get_quality_trend("improving_backend")
    assert trend.trend == "improving", f"Expected improving, got {trend.trend}"


def test_stable_trend_detected():
    for _ in range(20):
        quality_history.record_quality("stable_backend", 75.0)
    trend = quality_history.get_quality_trend("stable_backend")
    assert trend.trend == "stable", f"Expected stable, got {trend.trend}"


def test_insufficient_samples_returns_stable():
    for _ in range(3):
        quality_history.record_quality("few_samples", 80.0)
    trend = quality_history.get_quality_trend("few_samples")
    assert trend.trend == "stable"  # < TREND_MIN_SAMPLES


# ── Ring buffer behavior ────────────────────────────────────────────────────

def test_ring_buffer_capacity():
    for i in range(100):
        quality_history.record_quality("overflow_test", float(i))
    trend = quality_history.get_quality_trend("overflow_test")
    assert trend.sample_count == quality_history.QUALITY_HISTORY_SIZE


def test_ring_buffer_keeps_recent():
    for i in range(60):
        quality_history.record_quality("recent_test", float(i))
    trend = quality_history.get_quality_trend("recent_test")
    # Should keep last 50: scores 10-59, avg = 34.5
    assert trend.average > 30.0


# ── Routing score factor ─────────────────────────────────────────────────────

def test_routing_score_neutral_for_new_backend():
    factor = quality_history.get_quality_score_for_routing("brand_new")
    assert factor == 1.0


def test_routing_score_penalizes_declining():
    for _ in range(10):
        quality_history.record_quality("bad_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 20.0)
    factor = quality_history.get_quality_score_for_routing("bad_backend")
    assert factor < 1.0, f"Expected penalty for declining quality, got {factor}"


def test_routing_score_rewards_improving():
    for _ in range(10):
        quality_history.record_quality("good_backend", 20.0)
    for _ in range(10):
        quality_history.record_quality("good_backend", 90.0)
    factor = quality_history.get_quality_score_for_routing("good_backend")
    assert factor > 1.0, f"Expected boost for improving quality, got {factor}"


# ── get_all_trends ───────────────────────────────────────────────────────────

def test_get_all_trends():
    quality_history.record_quality("alpha", 80.0)
    quality_history.record_quality("beta", 60.0)
    trends = quality_history.get_all_trends()
    assert "alpha" in trends
    assert "beta" in trends
    assert trends["alpha"].average == 80.0
    assert trends["beta"].average == 60.0


# ── Recent average ───────────────────────────────────────────────────────────

def test_recent_average():
    for _ in range(20):
        quality_history.record_quality("recent_avg_test", 50.0)
    for _ in range(5):
        quality_history.record_quality("recent_avg_test", 90.0)
    trend = quality_history.get_quality_trend("recent_avg_test")
    # Recent 10: 5 from old (50.0) + 5 new (90.0) = avg 70.0
    assert trend.recent_average == 70.0


# ── Reset ────────────────────────────────────────────────────────────────────

def test_reset_all():
    quality_history.record_quality("test", 80.0)
    quality_history.reset_all()
    trend = quality_history.get_quality_trend("test")
    assert trend.sample_count == 0
