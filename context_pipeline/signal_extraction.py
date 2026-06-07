"""Signal Extraction — Evolver-inspired automatic evolution signal detection.

Scans event logs for patterns that should trigger evolution strategy changes:
- High error rate → switch to REPAIR
- Consistent success → switch to INNOVATE
- Backend-specific failures → record lesson + adjust weights
- Latency spikes → trigger harden mode
"""

import logging

from context_pipeline.event_log import EventLog, EventType
from context_pipeline.evolution import EvolutionStrategy, auto_select_strategy

_log = logging.getLogger(__name__)


def extract_signals(log: EventLog) -> dict:
    """Extract evolution signals from the event log, including quality trends."""
    events = log.events
    if not events:
        return {"error_rate": 0.0, "fallback_rate": 0.0, "quality_trend": "stable", "signals": []}

    total = len(events)
    errors = log.filter_by_type(EventType.RESPONSE_ERROR)
    fallbacks = log.filter_by_type(EventType.FALLBACK_TRIGGERED)
    successes = log.filter_by_type(EventType.RESPONSE_RECEIVED)

    error_rate = len(errors) / max(total, 1)
    fallback_rate = len(fallbacks) / max(total, 1)

    signals = []

    if error_rate > 0.5:
        signals.append({"type": "critical_error_rate", "value": error_rate})
    elif error_rate > 0.2:
        signals.append({"type": "elevated_error_rate", "value": error_rate})

    if fallback_rate > 0.3:
        signals.append({"type": "high_fallback_rate", "value": fallback_rate})

    # Detect backend-specific failure patterns
    backend_errors: dict[str, int] = {}
    for e in errors:
        backend = e.data.get("backend", "unknown")
        backend_errors[backend] = backend_errors.get(backend, 0) + 1

    for backend, count in backend_errors.items():
        if count >= 3:
            signals.append({
                "type": "backend_repeated_failure",
                "backend": backend,
                "count": count,
            })

    # Detect latency spikes
    latencies = [
        e.data.get("latency_ms", 0)
        for e in successes if e.data.get("latency_ms")
    ]
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        if avg_latency > 10000:
            signals.append({"type": "latency_spike", "avg_ms": int(avg_latency)})

    # Extract overall quality trend from quality_history
    overall_quality_trend = "stable"
    try:
        import quality_history
        all_trends = quality_history.get_all_trends()
        if all_trends:
            declining_count = sum(1 for t in all_trends.values() if t.trend == "declining")
            improving_count = sum(1 for t in all_trends.values() if t.trend == "improving")
            total_tracked = len(all_trends)

            if declining_count > total_tracked * 0.3:
                overall_quality_trend = "declining"
                signals.append({
                    "type": "quality_declining",
                    "declining_backends": declining_count,
                    "total_tracked": total_tracked,
                })
            elif improving_count > total_tracked * 0.3:
                overall_quality_trend = "improving"
                signals.append({
                    "type": "quality_improving",
                    "improving_backends": improving_count,
                    "total_tracked": total_tracked,
                })
    except ImportError:
        _log.debug("signal_extraction: quality_history not available", exc_info=True)

    return {
        "error_rate": round(error_rate, 3),
        "fallback_rate": round(fallback_rate, 3),
        "quality_trend": overall_quality_trend,
        "signals": signals,
    }


def recommend_strategy_from_signals(signals: dict, backends_available: int = 10) -> EvolutionStrategy:
    """Recommend an evolution strategy based on extracted signals including quality."""
    return auto_select_strategy(
        recent_error_rate=signals["error_rate"],
        recent_fallback_rate=signals["fallback_rate"],
        backends_available=backends_available,
        quality_trend=signals.get("quality_trend", "stable"),
    )
