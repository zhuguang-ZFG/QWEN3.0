"""Shared health models, constants, and in-memory state for the health subsystem."""

from __future__ import annotations

import threading
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
QUALITY_PENALTY_DURATION = 1800

_lock = threading.RLock()
_health_map: dict[str, str] = {}
_cooldown_states: dict[str, "CooldownState"] = {}
_quality_states: dict[str, "QualityState"] = {}
_quality_penalties: dict[str, float] = {}


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

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0


def calc_cooldown(failures: int, error_code: Optional[int] = None) -> float:
    if error_code in (401, 403):
        return COOLDOWN_AUTH_FIXED
    base = COOLDOWN_429_BASE if error_code == 429 else BASE_COOLDOWN
    cooldown = base * (BACKOFF_FACTOR ** (failures - 1))
    return min(cooldown, MAX_COOLDOWN)
