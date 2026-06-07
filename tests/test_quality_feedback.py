"""Tests for quality feedback loop in evolution strategy selection.

Verifies that:
- Declining quality triggers HARDEN strategy
- Improving quality enables INNOVATE strategy
- High error rates override quality signals (safety first)
- Signal extraction detects quality trends from quality_history
- Full feedback loop: record quality -> extract signals -> select strategy
"""

from unittest.mock import patch

import quality_history
from context_pipeline.evolution import (
    EvolutionStrategy,
    auto_select_strategy,
)


def setup_function():
    quality_history.reset_all()


# ── auto_select_strategy with quality_trend ──────────────────────────────────

def test_declining_quality_triggers_harden():
    """Declining quality should push toward HARDEN even with moderate error rates."""
    strategy = auto_select_strategy(
        recent_error_rate=0.08,
        recent_fallback_rate=0.15,
        backends_available=10,
        quality_trend="declining",
    )
    assert strategy == EvolutionStrategy.HARDEN, (
        f"Expected HARDEN for declining quality, got {strategy}"
    )


def test_declining_quality_with_low_errors_stays_balanced_or_harden():
    """Declining quality with very low error rate: BALANCED or HARDEN are both valid."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="declining",
    )
    # Very low errors + declining quality: may stay BALANCED or go HARDEN
    assert strategy in (EvolutionStrategy.BALANCED, EvolutionStrategy.HARDEN)


def test_improving_quality_enables_innovate():
    """Improving quality with low errors should enable INNOVATE."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="improving",
    )
    assert strategy == EvolutionStrategy.INNOVATE, (
        f"Expected INNOVATE for improving quality, got {strategy}"
    )


def test_stable_quality_normal_selection():
    """Stable quality should follow normal error/fallback based selection."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="stable",
    )
    assert strategy == EvolutionStrategy.INNOVATE  # low error + low fallback


def test_high_error_rate_overrides_quality():
    """High error rate should trigger REPAIR regardless of quality trend."""
    for trend in ("improving", "stable", "declining"):
        strategy = auto_select_strategy(
            recent_error_rate=0.6,
            recent_fallback_rate=0.1,
            backends_available=10,
            quality_trend=trend,
        )
        assert strategy == EvolutionStrategy.REPAIR, (
            f"Expected REPAIR for high error rate with {trend} quality, got {strategy}"
        )


def test_few_backends_overrides_quality():
    """Very few available backends should trigger REPAIR regardless of quality."""
    for trend in ("improving", "stable", "declining"):
        strategy = auto_select_strategy(
            recent_error_rate=0.1,
            recent_fallback_rate=0.1,
            backends_available=2,
            quality_trend=trend,
        )
        assert strategy == EvolutionStrategy.REPAIR


def test_backward_compatible_without_quality_trend():
    """auto_select_strategy should work without quality_trend parameter."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
    )
    # Should not crash, default to stable
    assert strategy in (EvolutionStrategy.INNOVATE, EvolutionStrategy.BALANCED)


# ── signal_extraction with quality ───────────────────────────────────────────

def test_extract_signals_includes_quality_trend():
    """extract_signals should include quality_trend in its output."""
    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals

    log = EventLog()
    for _ in range(10):
        log.emit(EventType.RESPONSE_RECEIVED, backend="a", latency_ms=500)

    signals = extract_signals(log)
    assert "quality_trend" in signals
    assert signals["quality_trend"] in ("improving", "declining", "stable")


def test_extract_signals_detects_declining_quality():
    """extract_signals should detect when many backends have declining quality."""
    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals

    # Set up declining quality for multiple backends
    for _ in range(15):
        quality_history.record_quality("b1", 90.0)
    for _ in range(15):
        quality_history.record_quality("b1", 20.0)
    for _ in range(15):
        quality_history.record_quality("b2", 90.0)
    for _ in range(15):
        quality_history.record_quality("b2", 20.0)

    log = EventLog()
    for _ in range(10):
        log.emit(EventType.RESPONSE_RECEIVED, backend="b1", latency_ms=500)

    signals = extract_signals(log)
    assert signals["quality_trend"] == "declining"
    quality_signals = [s for s in signals["signals"] if s["type"] == "quality_declining"]
    assert len(quality_signals) > 0


def test_recommend_strategy_uses_quality():
    """recommend_strategy_from_signals should pass quality_trend to auto_select."""
    from context_pipeline.signal_extraction import recommend_strategy_from_signals

    signals = {
        "error_rate": 0.08,
        "fallback_rate": 0.25,
        "quality_trend": "declining",
    }
    strategy = recommend_strategy_from_signals(signals, backends_available=10)
    assert strategy == EvolutionStrategy.HARDEN


def test_recommend_strategy_innovate_with_improving_quality():
    """recommend_strategy_from_signals should enable INNOVATE with improving quality."""
    from context_pipeline.signal_extraction import recommend_strategy_from_signals

    signals = {
        "error_rate": 0.02,
        "fallback_rate": 0.05,
        "quality_trend": "improving",
    }
    strategy = recommend_strategy_from_signals(signals, backends_available=10)
    assert strategy == EvolutionStrategy.INNOVATE


# ── End-to-end feedback loop ─────────────────────────────────────────────────

def test_feedback_loop_quality_drives_strategy():
    """Full loop: record quality scores -> extract signals -> select strategy."""
    # Simulate a system where quality is declining
    for _ in range(20):
        quality_history.record_quality("main_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("main_backend", 25.0)

    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals, recommend_strategy_from_signals

    log = EventLog()
    for _ in range(15):
        log.emit(EventType.RESPONSE_RECEIVED, backend="main_backend", latency_ms=800)
    for _ in range(3):
        log.emit(EventType.RESPONSE_ERROR, backend="main_backend", error="timeout")

    signals = extract_signals(log)
    strategy = recommend_strategy_from_signals(signals, backends_available=8)

    # With declining quality and some errors, should HARDEN
    assert strategy == EvolutionStrategy.HARDEN, (
        f"Expected HARDEN for declining quality system, got {strategy}"
    )
