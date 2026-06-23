"""Health scoring, degradation detection, and response quality (CQ-014 slice 9)."""

from __future__ import annotations

import time
from collections import Counter

from health_models import (
    BASE_COOLDOWN,
    QUALITY_PENALTY_DURATION,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_penalties,
    _quality_states,
)

_REFUSAL_PATTERNS = [
    "i cannot",
    "i can't",
    "i apologize",
    "i'm sorry but i",
    "as an ai",
    "i'm not able to",
    "i don't have the ability",
    "无法为你",
    "抱歉，我无法",
    "作为AI",
    "我没有能力",
]


def compute_score(backend: str) -> float:
    with _lock:
        quality = _quality_states.get(backend)
        if not quality or quality.total_requests == 0:
            return 50.0

        state = _cooldown_states.get(backend)
        failures = state.consecutive_failures if state else 0
        success_factor = max(0, 1.0 - failures * 0.2)

        if quality.latencies:
            avg_lat = sum(quality.latencies) / len(quality.latencies)
            latency_factor = 1.0 - min(avg_lat / 5000, 1.0)
        else:
            latency_factor = 0.5

        if quality.last_success > 0:
            age = time.monotonic() - quality.last_success
            recency_factor = 1.0 - min(age / 300, 1.0)
        else:
            recency_factor = 0.0

        score = success_factor * 50 + latency_factor * 30 + recency_factor * 20
        return round(max(0, min(100, score)), 1)


def get_scores() -> dict[str, float]:
    with _lock:
        backends = set(list(_health_map.keys()) + list(_quality_states.keys()))
    return {name: compute_score(name) for name in backends}


def detect_degradation(backend: str) -> str:
    with _lock:
        quality = _quality_states.get(backend)
        if not quality:
            return "healthy"

        if quality.empty_count >= 3:
            return "dead"

        if quality.total_requests >= 5 and quality.error_msg_count > quality.total_requests * 0.5:
            return "dead"

        if len(quality.response_lengths) >= 10:
            recent = list(quality.response_lengths)[-5:]
            historical = list(quality.response_lengths)
            recent_avg = sum(recent) / len(recent) if recent else 0
            hist_avg = sum(historical) / len(historical) if historical else 1
            if hist_avg > 0 and recent_avg < hist_avg * 0.3:
                return "degraded"

        return "healthy"


def detect_and_reset_mass_failure() -> bool:
    with _lock:
        if not _health_map:
            return False
        dead = sum(1 for status in _health_map.values() if status == "dead")
        if dead > len(_health_map) * 0.5:
            _health_map.clear()
            _cooldown_states.clear()
            _quality_states.clear()
            _quality_penalties.clear()
            return True
    return False


def get_backend_status(backend: str) -> dict:
    with _lock:
        state = _cooldown_states.get(backend)
        quality = _quality_states.get(backend)
        return {
            "health": _health_map.get(backend, "healthy"),
            "score": compute_score(backend),
            "cooldown_remaining": max(0, state.cooldown_until - time.monotonic()) if state else 0,
            "consecutive_failures": state.consecutive_failures if state else 0,
            "current_cooldown_s": state.current_cooldown if state else BASE_COOLDOWN,
            "last_error_code": state.last_error_code if state else None,
            "avg_latency_ms": (sum(quality.latencies) / len(quality.latencies))
            if quality and quality.latencies
            else None,
            "total_requests": quality.total_requests if quality else 0,
            "empty_count": quality.empty_count if quality else 0,
            "error_msg_count": quality.error_msg_count if quality else 0,
        }


def score_response_quality(
    response: str,
    query: str = "",
    expect_code: bool = False,
) -> float:
    if not response or not response.strip():
        return 0.0

    score = 1.0
    text = response.strip()
    text_lower = text.lower()

    for pattern in _REFUSAL_PATTERNS:
        if pattern in text_lower:
            score -= 0.4
            break

    if len(text) > 100 and text[-1] not in ".!?。！？\n```":
        last_line = text.split("\n")[-1]
        if len(last_line) > 20 and last_line[-1] not in ".!?。！？}])":
            score -= 0.2

    words = text.split()
    if len(words) > 30:
        chunks = [" ".join(words[i : i + 5]) for i in range(0, len(words) - 5, 5)]
        chunk_counts = Counter(chunks)
        if chunk_counts and chunk_counts.most_common(1)[0][1] >= 3:
            score -= 0.5

    if expect_code and "```" not in text and "def " not in text and "function" not in text:
        score -= 0.3

    if len(query) > 30 and len(text) < 20:
        score -= 0.3

    return max(0.0, min(1.0, score))


def record_quality_score(backend: str, quality: float) -> None:
    with _lock:
        state = _quality_states.setdefault(backend, QualityState())
        state.total_requests += 1

        if quality < 0.4:
            state.error_msg_count += 1
            if state.error_msg_count >= 3:
                _quality_penalties[backend] = time.monotonic() + QUALITY_PENALTY_DURATION
        else:
            state.error_msg_count = max(0, state.error_msg_count - 1)


def get_quality_penalty(backend: str) -> float:
    with _lock:
        deadline = _quality_penalties.get(backend, 0)
    if deadline and time.monotonic() < deadline:
        return 0.3
    return 1.0
