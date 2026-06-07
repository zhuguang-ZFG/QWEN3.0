"""End-to-end integration tests: semantic quality evaluation with feedback loop.

Tests the full pipeline:
1. Backend produces a response
2. Semantic evaluator scores it
3. Score is recorded in quality_history
4. Quality trend influences routing selection
5. Quality trend influences evolution strategy

All external dependencies are mocked where needed.
"""

from unittest.mock import MagicMock, patch

import quality_history
import route_scorer
import semantic_eval
from context_pipeline.evolution import EvolutionStrategy, auto_select_strategy


def setup_function():
    quality_history.reset_all()


# ── Scenario 1: High-quality backend gets rewarded ───────────────────────────

def test_high_quality_backend_rises_in_rankings():
    """A backend producing high-quality responses should rise in routing rankings."""
    # Simulate 20 high-quality responses from backend_a
    for _ in range(20):
        score = semantic_eval.evaluate_response(
            "How to implement a binary search tree",
            "Here is a complete implementation of a BST with insert, search, and delete operations. "
            "Each node has a value, left child, and right child. The left subtree contains only "
            "nodes with values less than the parent, and the right subtree contains only nodes "
            "with values greater.",
        )
        quality_history.record_quality("backend_a", score.total)

    # Simulate 20 low-quality responses from backend_b
    for _ in range(20):
        score = semantic_eval.evaluate_response(
            "How to implement a binary search tree",
            "The weather is nice today.",
        )
        quality_history.record_quality("backend_b", score.total)

    # Check routing factors
    factor_a = quality_history.get_quality_score_for_routing("backend_a")
    factor_b = quality_history.get_quality_score_for_routing("backend_b")

    assert factor_a > factor_b, (
        f"High-quality backend_a ({factor_a}) should rank higher "
        f"than low-quality backend_b ({factor_b})"
    )

    # Verify through route_scorer
    score_a = route_scorer.effective_score(
        "backend_a", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=factor_a,
    )
    score_b = route_scorer.effective_score(
        "backend_b", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=factor_b,
    )
    assert score_a > score_b


# ── Scenario 2: Quality decline triggers strategy shift ──────────────────────

def test_quality_decline_triggers_harden():
    """When quality starts declining, evolution strategy should shift to HARDEN."""
    # Phase 1: good quality
    for _ in range(15):
        quality_history.record_quality("primary", 85.0)

    trend_1 = quality_history.get_quality_trend("primary")
    strategy_1 = auto_select_strategy(
        recent_error_rate=0.05,
        recent_fallback_rate=0.1,
        backends_available=8,
        quality_trend=trend_1.trend,
    )

    # Phase 2: quality drops
    for _ in range(15):
        quality_history.record_quality("primary", 20.0)

    trend_2 = quality_history.get_quality_trend("primary")
    strategy_2 = auto_select_strategy(
        recent_error_rate=0.08,
        recent_fallback_rate=0.2,
        backends_available=8,
        quality_trend=trend_2.trend,
    )

    assert trend_2.trend == "declining"
    assert strategy_2 == EvolutionStrategy.HARDEN


# ── Scenario 3: Quality recovery enables innovation ──────────────────────────

def test_quality_recovery_enables_innovate():
    """After quality recovers and improves, strategy should shift to INNOVATE."""
    # Phase 1: declining
    for _ in range(15):
        quality_history.record_quality("recovering", 80.0)
    for _ in range(15):
        quality_history.record_quality("recovering", 30.0)

    trend_bad = quality_history.get_quality_trend("recovering")
    assert trend_bad.trend == "declining"

    # Phase 2: recovery + improvement (ring buffer keeps last 50)
    for _ in range(30):
        quality_history.record_quality("recovering", 90.0)

    trend_good = quality_history.get_quality_trend("recovering")
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.03,
        backends_available=10,
        quality_trend=trend_good.trend,
    )
    assert strategy == EvolutionStrategy.INNOVATE


# ── Scenario 4: Full pipeline simulation ─────────────────────────────────────

def test_full_pipeline_simulation():
    """Simulate a complete request lifecycle with semantic quality evaluation."""
    from context_pipeline.response_pipeline import ResponseContext
    from context_pipeline.response_processors import build_default_response_pipeline

    # Setup: two backends with different quality histories
    for _ in range(20):
        quality_history.record_quality("fast_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("slow_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("slow_backend", 25.0)

    # Process a response through the pipeline
    pipeline = build_default_response_pipeline()
    ctx = ResponseContext(
        backend="fast_backend",
        response_text=(
            "To implement a hash map in Python, you can use the built-in dict type "
            "or create a custom implementation with buckets and hash functions. "
            "Here is a basic implementation using separate chaining for collision resolution."
        ),
        status_code=200,
        latency_ms=400,
    )
    ctx.query = "How to implement a hash map in Python"

    result = pipeline.process(ctx)

    # Verify semantic_quality processor ran
    assert "semantic_quality" in result.processors_applied

    # Verify quality was recorded for fast_backend
    trend = quality_history.get_quality_trend("fast_backend")
    assert trend.sample_count == 21  # 20 historical + 1 from pipeline

    # Verify routing ranking
    ranked = route_scorer.rank_backends(
        ["fast_backend", "slow_backend"],
        "chat", "coding",
        health_scores={"fast_backend": 80.0, "slow_backend": 80.0},
        states={"fast_backend": {"state": "ok"}, "slow_backend": {"state": "ok"}},
        latency_map={"fast_backend": 400.0, "slow_backend": 400.0},
        quality_trends={
            "fast_backend": quality_history.get_quality_score_for_routing("fast_backend"),
            "slow_backend": quality_history.get_quality_score_for_routing("slow_backend"),
        },
    )
    assert ranked[0] == "fast_backend", (
        f"fast_backend should rank first, got {ranked}"
    )


# ── Scenario 5: Semantic evaluator distinguishes quality levels ──────────────

def test_semantic_evaluator_distinguishes_quality_levels():
    """Verify the evaluator produces meaningfully different scores for different quality."""
    query = "Explain how garbage collection works in Python"

    # High quality response
    high_quality = semantic_eval.evaluate_response(
        query,
        "Python uses reference counting as its primary garbage collection mechanism. "
        "Each object has a reference count that tracks how many references point to it. "
        "When the count reaches zero, the object is deallocated. Python also has a "
        "generational garbage collector (gc module) that handles reference cycles. "
        "Objects are organized into three generations, and the collector periodically "
        "scans for unreachable cycles.",
    )

    # Low quality response (irrelevant)
    low_quality = semantic_eval.evaluate_response(
        query,
        "The capital of Japan is Tokyo. It has a population of about 14 million people. "
        "Mount Fuji is a famous landmark nearby.",
    )

    # Empty response
    empty = semantic_eval.evaluate_response(query, "")

    assert high_quality.total > low_quality.total, (
        f"High quality ({high_quality.total}) should score higher "
        f"than low quality ({low_quality.total})"
    )
    assert low_quality.total > empty.total, (
        f"Low quality ({low_quality.total}) should score higher "
        f"than empty ({empty.total})"
    )
    assert high_quality.relevance > low_quality.relevance
    assert high_quality.total >= 60
    assert empty.total <= 30


# ── Scenario 6: Quality-weighted ranking with multiple factors ────────────────

def test_quality_factor_combined_with_other_factors():
    """Quality factor should work alongside health, latency, and quota."""
    # Backend A: great health, fast, but declining quality
    score_a = route_scorer.effective_score(
        "backend_a", "chat", "coding",
        health_score=90.0,
        state={"state": "ok"},
        avg_latency_ms=300.0,
        remaining_quota_score=1.0,
        quality_trend_score=0.7,  # declining
    )

    # Backend B: good health, moderate latency, improving quality
    score_b = route_scorer.effective_score(
        "backend_b", "chat", "coding",
        health_score=75.0,
        state={"state": "ok"},
        avg_latency_ms=800.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.3,  # improving
    )

    # Both should produce valid scores
    assert 0.0 < score_a < 1.0
    assert 0.0 < score_b < 1.0

    # Verify quality factor produces measurable separation when other factors are equal
    score_same_declining = route_scorer.effective_score(
        "backend_c", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=0.7,
    )
    score_same_improving = route_scorer.effective_score(
        "backend_c", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=1.3,
    )
    assert score_same_improving > score_same_declining, (
        f"Improving ({score_same_improving}) should outscore "
        f"declining ({score_same_declining}) when other factors are equal"
    )


# ── Scenario 7: New backend with no quality data ─────────────────────────────

def test_new_backend_gets_neutral_quality():
    """A new backend with no quality history should get neutral quality factor."""
    factor = quality_history.get_quality_score_for_routing("brand_new_backend")
    assert factor == 1.0

    score = route_scorer.effective_score(
        "brand_new_backend", "chat", "coding",
        health_score=50.0,
        avg_latency_ms=1000.0,
        remaining_quota_score=1.0,
        quality_trend_score=factor,
    )
    assert score > 0.0
