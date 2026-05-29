"""In-memory, zero-dependency metrics aggregation for LiMa events."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

from observability.events import LiMaEvent

logger = logging.getLogger(__name__)

_lock = threading.Lock()

_total_requests: int = 0
_success: dict[str, int] = defaultdict(int)
_failure: dict[str, int] = defaultdict(int)
_failure_class_counts: dict[str, int] = defaultdict(int)
_event_type_counts: dict[str, int] = defaultdict(int)

_latency_samples: dict[str, list[float]] = defaultdict(list)
MAX_LATENCY_SAMPLES = 200

_quality_samples: dict[str, list[float]] = defaultdict(list)
MAX_QUALITY_SAMPLES = 200

_token_prompt: dict[str, int] = defaultdict(int)
_token_completion: dict[str, int] = defaultdict(int)
_token_requests: dict[str, int] = defaultdict(int)

_session_backends: dict[str, str] = {}
MAX_SESSIONS = 1000

_start_time: float = time.time()


def record(event: LiMaEvent) -> None:
    """Record a single LiMaEvent into aggregated metrics."""
    global _total_requests
    with _lock:
        _event_type_counts[event.event_type] += 1

        if event.event_type == "request_start":
            _total_requests += 1

        elif event.event_type == "backend_call":
            _success[event.backend] += 1
            if event.latency_ms >= 0:
                samples = _latency_samples[event.backend]
                samples.append(event.latency_ms)
                if len(samples) > MAX_LATENCY_SAMPLES:
                    _latency_samples[event.backend] = samples[-MAX_LATENCY_SAMPLES:]
            if event.session_id_hash:
                _prune_sessions()
                _session_backends[event.session_id_hash] = event.backend

        elif event.event_type == "backend_error":
            _failure[event.backend] += 1
            if event.failure_class:
                _failure_class_counts[event.failure_class] += 1

        elif event.event_type == "quality_result":
            if event.quality_score >= 0:
                samples = _quality_samples[event.backend]
                samples.append(event.quality_score)
                if len(samples) > MAX_QUALITY_SAMPLES:
                    _quality_samples[event.backend] = samples[-MAX_QUALITY_SAMPLES:]

        elif event.event_type == "token_usage":
            _token_prompt[event.backend] += event.prompt_tokens
            _token_completion[event.backend] += event.completion_tokens
            _token_requests[event.backend] += 1

    try:
        from observability.openobserve_sink import maybe_export_event

        maybe_export_event(event)
    except ImportError:
        logger.debug("openobserve sink unavailable")
    except Exception:
        logger.debug("openobserve export skipped", exc_info=True)


def _prune_sessions() -> None:
    if len(_session_backends) > MAX_SESSIONS:
        oldest = sorted(_session_backends.keys())[:500]
        for key in oldest:
            _session_backends.pop(key, None)


def get_metrics_snapshot() -> dict:
    """Return a complete redacted metrics snapshot suitable for APIs/admin."""
    with _lock:
        backend_stats = {}
        all_backends = (
            set(_success.keys())
            | set(_failure.keys())
            | set(_quality_samples.keys())
            | set(_token_requests.keys())
        )
        for backend in sorted(all_backends):
            latencies = _latency_samples.get(backend, [])
            quality = _quality_samples.get(backend, [])
            backend_stats[backend] = {
                "success": _success.get(backend, 0),
                "failure": _failure.get(backend, 0),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1)
                if latencies else 0,
                "p50_latency_ms": _percentile(latencies, 50),
                "p95_latency_ms": _percentile(latencies, 95),
                "avg_quality_score": round(sum(quality) / len(quality), 2)
                if quality else 0,
                "prompt_tokens": _token_prompt.get(backend, 0),
                "completion_tokens": _token_completion.get(backend, 0),
                "token_requests": _token_requests.get(backend, 0),
            }

        top_failures = sorted(_failure_class_counts.items(), key=lambda item: -item[1])[:10]
        return {
            "uptime_seconds": round(time.time() - _start_time, 1),
            "total_requests": _total_requests,
            "active_sessions": len(_session_backends),
            "backends": backend_stats,
            "failure_class_counts": dict(top_failures),
            "event_type_counts": dict(_event_type_counts),
        }


def get_top_failing_backends(n: int = 5) -> list[tuple[str, int]]:
    """Return backends ordered by failure count."""
    with _lock:
        return sorted(_failure.items(), key=lambda item: -item[1])[:n]


def get_top_quality_backends(n: int = 5) -> list[tuple[str, float]]:
    """Return backends ordered by average quality score."""
    with _lock:
        scored = []
        for backend, samples in _quality_samples.items():
            if len(samples) >= 3:
                scored.append((backend, round(sum(samples) / len(samples), 2)))
        return sorted(scored, key=lambda item: -item[1])[:n]


def get_fastest_growing_failure_class(n: int = 5) -> list[tuple[str, int]]:
    """Return failure classes ordered by count."""
    with _lock:
        return sorted(_failure_class_counts.items(), key=lambda item: -item[1])[:n]


def _percentile(samples: list[float], p: int) -> float:
    if not samples:
        return 0.0
    sorted_samples = sorted(samples)
    idx = int(len(sorted_samples) * p / 100)
    idx = min(idx, len(sorted_samples) - 1)
    return round(sorted_samples[idx], 1)


def reset_metrics() -> None:
    """Clear all metrics state. For test isolation only."""
    global _total_requests, _start_time
    with _lock:
        _total_requests = 0
        _start_time = time.time()
        _success.clear()
        _failure.clear()
        _failure_class_counts.clear()
        _event_type_counts.clear()
        _latency_samples.clear()
        _quality_samples.clear()
        _token_prompt.clear()
        _token_completion.clear()
        _token_requests.clear()
        _session_backends.clear()
