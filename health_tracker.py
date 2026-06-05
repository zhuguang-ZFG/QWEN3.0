"""
LiMa Health Tracker v2 — thin re-export layer (CQ-014 slice 9).

Modules:
  health_failure_classifier.py  classify_failure
  health_state.py               cooldown state + getters
  health_recorder.py            record_success / record_failure
  health_scoring.py             scores, degradation, response quality
"""

from health_failure_classifier import classify_failure
from health_recorder import record_failure, record_response_quality, record_success
from health_scoring import (
    compute_score,
    detect_and_reset_mass_failure,
    detect_degradation,
    get_backend_status,
    get_quality_penalty,
    get_scores,
    record_quality_score,
    score_response_quality,
)
from health_state import (
    BACKOFF_FACTOR,
    BASE_COOLDOWN,
    COOLDOWN_429_BASE,
    COOLDOWN_AUTH_FIXED,
    CooldownState,
    FAILURE_THRESHOLD_MIN_REQUESTS,
    LATENCY_PENALTY,
    LATENCY_WINDOW_SIZE,
    MAX_COOLDOWN,
    QUALITY_PENALTY_DURATION,
    QUALITY_WINDOW,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_penalties,
    _quality_states,
    get_backend_state,
    get_cooldown_remaining,
    get_health,
    get_health_map,
    get_latency_map,
    is_cooled_down,
    seed_backends,
    set_cooldown,
)

__all__ = [
    "BACKOFF_FACTOR",
    "BASE_COOLDOWN",
    "COOLDOWN_429_BASE",
    "COOLDOWN_AUTH_FIXED",
    "CooldownState",
    "FAILURE_THRESHOLD_MIN_REQUESTS",
    "LATENCY_PENALTY",
    "LATENCY_WINDOW_SIZE",
    "MAX_COOLDOWN",
    "QUALITY_PENALTY_DURATION",
    "QUALITY_WINDOW",
    "QualityState",
    "classify_failure",
    "compute_score",
    "detect_and_reset_mass_failure",
    "detect_degradation",
    "get_backend_state",
    "get_backend_status",
    "get_cooldown_remaining",
    "get_health",
    "get_health_map",
    "get_latency_map",
    "get_quality_penalty",
    "get_scores",
    "is_cooled_down",
    "record_failure",
    "record_quality_score",
    "record_response_quality",
    "record_success",
    "score_response_quality",
    "seed_backends",
    "set_cooldown",
]
