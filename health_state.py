"""Shared health state, cooldown math, and read-only accessors (CQ-014 slice 9)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

BASE_COOLDOWN = 5
MAX_COOLDOWN = 300
BACKOFF_FACTOR = 2
COOLDOWN_429_BASE = 30
COOLDOWN_AUTH_FIXED = 300

QUALITY_WINDOW = 50
LATENCY_WINDOW_SIZE = 20
LATENCY_PENALTY = 5000.0
FAILURE_THRESHOLD_MIN_REQUESTS = 5

_lock = threading.RLock()
_health_map: dict[str, str] = {}
_cooldown_states: dict[str, "CooldownState"] = {}
_quality_states: dict[str, "QualityState"] = {}
_quality_penalties: dict[str, float] = {}
QUALITY_PENALTY_DURATION = 1800


@dataclass
class CooldownState:
    consecutive_failures: int = 0
    current_cooldown: float = BASE_COOLDOWN
    cooldown_until: float = 0.0
    last_error_code: Optional[int] = None
    state: str = "ok"
    last_error_class: Optional[str] = None


@dataclass
class QualityState:
    response_lengths: deque = field(default_factory=lambda: deque(maxlen=QUALITY_WINDOW))
    latencies: deque = field(default_factory=lambda: deque(maxlen=LATENCY_WINDOW_SIZE))
    empty_count: int = 0
    error_msg_count: int = 0
    total_requests: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0


def calc_cooldown(failures: int, error_code: Optional[int] = None) -> float:
    if error_code in (401, 403):
        return COOLDOWN_AUTH_FIXED
    base = COOLDOWN_429_BASE if error_code == 429 else BASE_COOLDOWN
    cooldown = base * (BACKOFF_FACTOR ** (failures - 1))
    return min(cooldown, MAX_COOLDOWN)


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
        return max(0, state.cooldown_until - time.monotonic())


def get_backend_state(backend: str) -> dict:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return {
                "state": "ok",
                "cooldown_until": 0.0,
                "last_error_class": None,
                "last_error_code": None,
            }
        return {
            "state": state.state,
            "cooldown_until": state.cooldown_until,
            "last_error_class": state.last_error_class,
            "last_error_code": state.last_error_code,
        }


def get_latency_map() -> dict:
    with _lock:
        result = {}
        for name, quality in _quality_states.items():
            if quality.latencies:
                result[name] = sum(quality.latencies) / len(quality.latencies)
            else:
                result[name] = 1000.0
        return result


def clear_cooldown(backend: str) -> None:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return
        state.cooldown_until = 0.0
        state.consecutive_failures = 0
        state.state = "ok"


def reset_all_state() -> None:
    with _lock:
        _health_map.clear()
        _cooldown_states.clear()
        _quality_states.clear()
        _quality_penalties.clear()
