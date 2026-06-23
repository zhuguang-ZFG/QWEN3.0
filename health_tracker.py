"""
LiMa Health Tracker v2 — thin re-export layer (CQ-014 slice 9).

Modules:
  health_models.py              constants + shared dataclasses
  health_state.py               cooldown state + getters
  health_recorder.py            record_success / record_failure / classify_failure
  health_scoring.py             scores, degradation, response quality
"""

from health_models import (
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
)
from health_recorder import (
    classify_failure,
    record_failure,
    record_response_quality,
    record_success,
)
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
    get_backend_state,
    get_cooldown_remaining,
    get_health,
    get_health_map,
    get_latency_map,
    is_cooled_down,
    reset_all_state,
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
    "reset_all_state",
    "score_response_quality",
    "set_cooldown",
]
