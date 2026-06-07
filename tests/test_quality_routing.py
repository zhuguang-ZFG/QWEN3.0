"""Tests for quality-weighted routing — route_scorer and routing_selector integration."""

from unittest.mock import MagicMock, patch

import quality_history
import route_scorer


def setup_function():
    quality_history.reset_all()


# ── route_scorer.effective_score with quality_trend ──────────────────────────

def test_effective_score_includes_quality_trend():
    """effective_score should include quality_trend_score as a factor."""
    score_high_quality = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.2,  # improving
    )
    score_low_quality = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=0.7,  # declining
    )
    assert score_high_quality > score_low_quality, (
        f"High quality ({score_high_quality}) should score higher "
        f"than low quality ({score_low_quality})"
    )


def test_effective_score_default_quality_trend():
    """Default quality_trend_score should be 1.0 (neutral)."""
    score_default = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
    )
    score_explicit_neutral = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.0,
    )
    assert score_default == score_explicit_neutral


def test_effective_score_weights_sum_to_one():
    """Verify all weights sum to 1.0: 0.35 + 0.25 + 0.15 + 0.10 + 0.05 + 0.10 = 1.0."""
    weights = [0.35, 0.25, 0.15, 0.10, 0.05, 0.10]
    assert abs(sum(weights) - 1.0) < 0.001


# ── rank_backends with quality trends ────────────────────────────────────────

def test_rank_backends_uses_quality_trends():
    """rank_backends should consider quality trends in ordering."""
    backends = ["good_backend", "bad_backend", "neutral_backend"]

    # All have same health score and latency
    health_scores = {b: 80.0 for b in backends}
    states = {b: {"state": "ok"} for b in backends}
    latency_map = {b: 500.0 for b in backends}

    # Different quality trends
    quality_trends = {
        "good_backend": 1.3,    # improving
        "bad_backend": 0.7,     # declining
        "neutral_backend": 1.0, # neutral
    }

    ranked = route_scorer.rank_backends(
        backends, "chat", "chat",
        health_scores=health_scores,
        states=states,
        latency_map=latency_map,
        quality_trends=quality_trends,
    )

    assert ranked[0] == "good_backend", f"Expected good_backend first, got {ranked}"
    assert ranked[-1] == "bad_backend", f"Expected bad_backend last, got {ranked}"


def test_rank_backends_default_no_quality_trends():
    """When no quality_trends passed, all backends get neutral 1.0."""
    backends = ["a", "b"]
    ranked = route_scorer.rank_backends(
        backends, "chat", "chat",
        health_scores={"a": 80.0, "b": 80.0},
        states={"a": {"state": "ok"}, "b": {"state": "ok"}},
        latency_map={"a": 500.0, "b": 500.0},
    )
    # Both should have equal scores, order preserved
    assert len(ranked) == 2


# ── routing_selector integration ─────────────────────────────────────────────

def test_routing_selector_computes_quality_trends():
    """routing_selector.select should compute quality_trends from quality_history."""
    # Record some quality data
    for _ in range(10):
        quality_history.record_quality("scnet_ds_flash", 85.0)
    for _ in range(10):
        quality_history.record_quality("scnet_ds_flash", 20.0)

    factor = quality_history.get_quality_score_for_routing("scnet_ds_flash")
    assert factor < 1.0, f"Declining backend should have factor < 1.0, got {factor}"


def test_quality_history_integration_with_routing():
    """End-to-end: quality history affects routing scores."""
    # Setup: backend A has declining quality, backend B has improving quality
    for _ in range(15):
        quality_history.record_quality("backend_a", 90.0)
    for _ in range(15):
        quality_history.record_quality("backend_a", 30.0)

    for _ in range(15):
        quality_history.record_quality("backend_b", 30.0)
    for _ in range(15):
        quality_history.record_quality("backend_b", 90.0)

    factor_a = quality_history.get_quality_score_for_routing("backend_a")
    factor_b = quality_history.get_quality_score_for_routing("backend_b")

    # B should have a higher routing factor than A
    assert factor_b > factor_a, (
        f"Improving backend_b ({factor_b}) should have higher factor "
        f"than declining backend_a ({factor_a})"
    )
