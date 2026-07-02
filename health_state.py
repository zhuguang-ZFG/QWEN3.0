"""Shared health state accessors and SQLite persistence (CQ-014 slice 9).

Modules:
  health_models.py              constants + shared dataclasses
  health_recorder.py            record_success / record_failure / classify_failure
  health_scoring.py             scores, degradation, response quality
  health_state_persistence.py   SQLite save/load with event-loop-safe debouncing
"""

from __future__ import annotations

import logging
import time


from health_models import (
    BASE_COOLDOWN,
    CooldownState,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_penalties,
    _quality_states,
)

logger = logging.getLogger(__name__)

# Re-export persistence functions so existing callers keep working.
from health_state_persistence import (
    flush_pending_save,  # noqa: F401  re-export imported by tests (hs.flush_pending_save)
    load_health_state,  # noqa: F401  re-export imported by tests
    save_health_state,  # noqa: F401  re-export imported by tests
    save_on_change,  # noqa: F401  re-export imported by tests
)


def get_health(backend: str) -> str:
    with _lock:
        return _health_map.get(backend, "healthy")


def get_health_map() -> dict:
    with _lock:
        return dict(_health_map)


def is_cooled_down(backend: str) -> bool:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return False
        return time.monotonic() <= state.cooldown_until


def set_cooldown(backend: str, ttl: float = BASE_COOLDOWN) -> None:
    with _lock:
        state = _cooldown_states.setdefault(backend, CooldownState())
        state.cooldown_until = time.monotonic() + ttl


def get_cooldown_remaining(backend: str) -> float:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return 0.0
        return max(0.0, state.cooldown_until - time.monotonic())


def get_backend_state(backend: str) -> dict:
    with _lock:
        state = _cooldown_states.get(backend, CooldownState())
        return {
            "consecutive_failures": state.consecutive_failures,
            "current_cooldown": state.current_cooldown,
            "cooldown_until": state.cooldown_until,
            "last_error_code": state.last_error_code,
            "state": state.state,
            "last_error_class": state.last_error_class,
        }


def get_backend_quality(backend: str) -> dict:
    with _lock:
        quality = _quality_states.get(backend, QualityState())
        return {
            "total_requests": quality.total_requests,
            "empty_count": quality.empty_count,
            "error_msg_count": quality.error_msg_count,
            "avg_latency_ms": quality.avg_latency,
            "last_success": quality.last_success,
            "last_failure": quality.last_failure,
        }


def get_quality_penalty(backend: str) -> float:
    with _lock:
        return _quality_penalties.get(backend, 0.0)


def set_quality_penalty(backend: str, penalty: float) -> None:
    with _lock:
        _quality_penalties[backend] = penalty


def get_latency_map() -> dict[str, float]:
    with _lock:
        return {backend: quality.avg_latency for backend, quality in _quality_states.items() if quality.avg_latency > 0}


def reset_all_state() -> None:
    with _lock:
        _health_map.clear()
        _cooldown_states.clear()
        _quality_states.clear()
        _quality_penalties.clear()
