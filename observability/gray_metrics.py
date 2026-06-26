"""Gray-observation counters for semantic cache and Instructor intent metrics."""

from __future__ import annotations

import threading
from collections import defaultdict

from observability.events import LiMaEvent

_lock = threading.Lock()

MAX_LATENCY_SAMPLES = 200

_semantic_cache_hit: int = 0
_semantic_cache_miss: int = 0
_semantic_cache_skip: int = 0
_semantic_cache_error: int = 0
_semantic_cache_store: int = 0
_semantic_cache_lookup_latency_samples: dict[str, list[float]] = defaultdict(list)

_instructor_intent_success: int = 0
_instructor_intent_failure: int = 0
_instructor_intent_skip: int = 0
_instructor_intent_latency_samples: dict[str, list[float]] = defaultdict(list)


def record_gray_event(event: LiMaEvent) -> None:
    """Update gray-observation counters for a single LiMaEvent."""
    global _semantic_cache_hit, _semantic_cache_miss, _semantic_cache_skip
    global _semantic_cache_error, _semantic_cache_store
    global _instructor_intent_success, _instructor_intent_failure, _instructor_intent_skip
    with _lock:
        if event.event_type.startswith("semantic_cache_"):
            kind = event.event_type[len("semantic_cache_") :]
            if kind == "hit":
                _semantic_cache_hit += 1
            elif kind == "miss":
                _semantic_cache_miss += 1
            elif kind == "skip":
                _semantic_cache_skip += 1
            elif kind == "error":
                _semantic_cache_error += 1
            elif kind == "store":
                _semantic_cache_store += 1
            if event.latency_ms >= 0 and kind in {"hit", "miss", "error"}:
                samples = _semantic_cache_lookup_latency_samples["semantic_cache"]
                samples.append(event.latency_ms)
                if len(samples) > MAX_LATENCY_SAMPLES:
                    _semantic_cache_lookup_latency_samples["semantic_cache"] = samples[-MAX_LATENCY_SAMPLES:]

        elif event.event_type == "instructor_intent_success":
            _instructor_intent_success += 1
        elif event.event_type == "instructor_intent_failure":
            _instructor_intent_failure += 1
        elif event.event_type == "instructor_intent_skip":
            _instructor_intent_skip += 1
        elif event.event_type == "instructor_intent_latency":
            if event.latency_ms >= 0:
                samples = _instructor_intent_latency_samples[event.backend]
                samples.append(event.latency_ms)
                if len(samples) > MAX_LATENCY_SAMPLES:
                    _instructor_intent_latency_samples[event.backend] = samples[-MAX_LATENCY_SAMPLES:]


def get_gray_observation() -> dict:
    """Return a snapshot of gray-observation counters and latency percentiles."""
    with _lock:
        semantic_lookup_latencies = _semantic_cache_lookup_latency_samples.get("semantic_cache", [])
        semantic_lookup_total = _semantic_cache_hit + _semantic_cache_miss + _semantic_cache_error

        all_instructor_latencies = [
            sample for samples in _instructor_intent_latency_samples.values() for sample in samples
        ]
        instructor_attempts = _instructor_intent_success + _instructor_intent_failure

        return {
            "semantic_cache": {
                "hit_rate": round(_semantic_cache_hit / semantic_lookup_total, 4) if semantic_lookup_total else 0.0,
                "avg_lookup_ms": round(sum(semantic_lookup_latencies) / len(semantic_lookup_latencies), 1)
                if semantic_lookup_latencies
                else 0,
                "p95_lookup_ms": _percentile(semantic_lookup_latencies, 95),
                "hit": _semantic_cache_hit,
                "miss": _semantic_cache_miss,
                "skip": _semantic_cache_skip,
                "error": _semantic_cache_error,
                "store": _semantic_cache_store,
            },
            "instructor_intent": {
                "success_rate": round(_instructor_intent_success / instructor_attempts, 4)
                if instructor_attempts
                else 0.0,
                "avg_latency_ms": round(sum(all_instructor_latencies) / len(all_instructor_latencies), 1)
                if all_instructor_latencies
                else 0,
                "p95_latency_ms": _percentile(all_instructor_latencies, 95),
                "success": _instructor_intent_success,
                "failure": _instructor_intent_failure,
                "skip": _instructor_intent_skip,
            },
        }


def reset_gray_metrics() -> None:
    """Clear all gray-observation state."""
    global _semantic_cache_hit, _semantic_cache_miss, _semantic_cache_skip
    global _semantic_cache_error, _semantic_cache_store
    global _instructor_intent_success, _instructor_intent_failure, _instructor_intent_skip
    with _lock:
        _semantic_cache_hit = 0
        _semantic_cache_miss = 0
        _semantic_cache_skip = 0
        _semantic_cache_error = 0
        _semantic_cache_store = 0
        _semantic_cache_lookup_latency_samples.clear()
        _instructor_intent_success = 0
        _instructor_intent_failure = 0
        _instructor_intent_skip = 0
        _instructor_intent_latency_samples.clear()


def _percentile(samples: list[float], p: int) -> float:
    if not samples:
        return 0.0
    sorted_samples = sorted(samples)
    idx = int(len(sorted_samples) * p / 100)
    idx = min(idx, len(sorted_samples) - 1)
    return round(sorted_samples[idx], 1)
