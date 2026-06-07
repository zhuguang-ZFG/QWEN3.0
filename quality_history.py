"""Quality history — per-backend semantic quality score persistence.

Stores quality scores in a ring buffer per backend. Provides trend analysis
including average, trend direction, and confidence interval.

Used by routing_selector to penalize backends with declining quality
and by evolution.py to choose explore/exploit/repair strategies.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

# ── Configuration ────────────────────────────────────────────────────────────

QUALITY_HISTORY_SIZE = 50  # ring buffer capacity per backend
TREND_MIN_SAMPLES = 5      # minimum samples before trend is meaningful
CONFIDENCE_Z = 1.96        # 95% confidence interval z-score

_lock = threading.RLock()
_quality_histories: dict[str, deque] = {}


@dataclass
class QualityTrend:
    """Summary of quality trend for a backend."""
    average: float          # 0-100 average quality score
    trend: str              # "improving", "declining", "stable"
    confidence: float       # 0.0-1.0 confidence in the trend direction
    sample_count: int       # number of samples in history
    recent_average: float   # 0-100 average of last 10 scores
    std_dev: float          # standard deviation of scores


# ── Core operations ──────────────────────────────────────────────────────────

def record_quality(backend: str, score: float) -> None:
    """Record a semantic quality score for a backend.

    Args:
        backend: Backend identifier.
        score: Quality score 0-100 (from semantic_eval.evaluate_response).
    """
    score = max(0.0, min(100.0, score))
    with _lock:
        hist = _quality_histories.setdefault(
            backend, deque(maxlen=QUALITY_HISTORY_SIZE)
        )
        hist.append((time.monotonic(), score))


def get_quality_trend(backend: str) -> QualityTrend:
    """Compute quality trend for a backend.

    Returns a QualityTrend with average, direction, and confidence.
    For backends with no history, returns neutral defaults.
    """
    with _lock:
        hist = _quality_histories.get(backend)
        if not hist:
            return QualityTrend(
                average=50.0, trend="stable", confidence=0.0,
                sample_count=0, recent_average=50.0, std_dev=0.0,
            )

        scores = [s for _, s in hist]
        n = len(scores)
        avg = sum(scores) / n

        # Standard deviation
        if n >= 2:
            variance = sum((s - avg) ** 2 for s in scores) / (n - 1)
            std = variance ** 0.5
        else:
            std = 0.0

        # Recent average (last 10)
        recent = scores[-10:]
        recent_avg = sum(recent) / len(recent)

        # Trend direction: compare recent half vs older half
        trend = "stable"
        confidence = 0.0
        if n >= TREND_MIN_SAMPLES:
            mid = n // 2
            older_half = scores[:mid]
            newer_half = scores[mid:]
            older_avg = sum(older_half) / len(older_half)
            newer_avg = sum(newer_half) / len(newer_half)
            diff = newer_avg - older_avg

            # Margin of error
            se = std / (n ** 0.5) if n > 1 else 0.0
            margin = CONFIDENCE_Z * se if se > 0 else 5.0

            if diff > margin:
                trend = "improving"
            elif diff < -margin:
                trend = "declining"

            # Confidence based on sample size and effect magnitude
            effect_size = abs(diff) / max(std, 1.0)
            confidence = min(1.0, (n / QUALITY_HISTORY_SIZE) * 0.5 + effect_size * 0.5)

        return QualityTrend(
            average=round(avg, 1),
            trend=trend,
            confidence=round(confidence, 3),
            sample_count=n,
            recent_average=round(recent_avg, 1),
            std_dev=round(std, 1),
        )


def get_all_trends() -> dict[str, QualityTrend]:
    """Return quality trends for all tracked backends."""
    with _lock:
        backends = list(_quality_histories.keys())
    return {b: get_quality_trend(b) for b in backends}


def get_quality_score_for_routing(backend: str) -> float:
    """Get a single quality factor (0.0-2.0) for use in routing score multiplication.

    Returns:
        - 1.0 if no history (neutral)
        - 0.7-0.9 if declining quality
        - 1.0-1.2 if improving quality
        - 0.95-1.05 if stable
    """
    trend = get_quality_trend(backend)
    if trend.sample_count < TREND_MIN_SAMPLES:
        return 1.0  # not enough data

    # Map average quality to a routing multiplier
    # Average 0-100 mapped to multiplier 0.7-1.3
    base = 0.7 + (trend.average / 100.0) * 0.6

    # Adjust by trend direction
    if trend.trend == "declining":
        base *= (1.0 - trend.confidence * 0.15)
    elif trend.trend == "improving":
        base *= (1.0 + trend.confidence * 0.1)

    return round(max(0.5, min(1.5, base)), 3)


def reset_all() -> None:
    """Clear all quality history (tests only)."""
    with _lock:
        _quality_histories.clear()
