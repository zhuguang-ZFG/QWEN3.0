"""Passive health recording (CQ-014 slice 9)."""

from __future__ import annotations

import logging
import time
from typing import Optional

_log = logging.getLogger(__name__)

from health_failure_classifier import classify_failure
from health_state import (
    BASE_COOLDOWN,
    COOLDOWN_AUTH_FIXED,
    FAILURE_THRESHOLD_MIN_REQUESTS,
    LATENCY_PENALTY,
    CooldownState,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_states,
    calc_cooldown,
)


def record_success(backend: str, latency_ms: float) -> None:
    with _lock:
        _health_map[backend] = "healthy"

        state = _cooldown_states.get(backend)
        if state:
            state.consecutive_failures = 0
            state.current_cooldown = BASE_COOLDOWN
            state.cooldown_until = 0.0
            state.state = "ok"
            state.last_error_class = None

        quality = _quality_states.setdefault(backend, QualityState())
        quality.latencies.append(latency_ms)
        quality.last_success = time.monotonic()
        quality.empty_count = max(0, quality.empty_count - 1)
        quality.total_requests += 1

    # Update backend profile (outside lock to avoid deadlock)
    try:
        import backend_profile
        backend_profile.record_request(backend, latency_ms, success=True)
    except ImportError:
        pass


def record_failure(
    backend: str,
    error_code: Optional[int] = None,
    error_text: str = "",
) -> None:
    with _lock:
        if error_code == 400:
            state = _cooldown_states.setdefault(backend, CooldownState())
            state.bad_request_count = getattr(state, "bad_request_count", 0) + 1
            return

        state = _cooldown_states.setdefault(backend, CooldownState())
        error_class = classify_failure(error_code, error_text)
        state.consecutive_failures += 1
        state.last_error_code = error_code
        state.state = error_class
        state.last_error_class = error_class
        if error_class in ("auth_expired", "manual_refresh_required", "quota_exhausted"):
            state.current_cooldown = COOLDOWN_AUTH_FIXED
        elif error_class == "rate_limited":
            state.current_cooldown = calc_cooldown(state.consecutive_failures, 429)
        else:
            state.current_cooldown = calc_cooldown(
                state.consecutive_failures, error_code
            )
        state.cooldown_until = time.monotonic() + state.current_cooldown

        quality = _quality_states.setdefault(backend, QualityState())
        quality.last_failure = time.monotonic()
        quality.total_requests += 1
        quality.latencies.append(LATENCY_PENALTY)

        old_health = _health_map.get(backend, "healthy")
        if error_class in ("auth_expired", "manual_refresh_required"):
            _health_map[backend] = "suspicious"
        elif error_class in ("rate_limited", "quota_exhausted"):
            _health_map[backend] = "degraded"
        elif state.consecutive_failures >= FAILURE_THRESHOLD_MIN_REQUESTS:
            _health_map[backend] = "dead"
        else:
            _health_map[backend] = "degraded"

        new_health = _health_map[backend]
        if old_health != new_health:
            try:
                from telegram_notify import notify_health_change

                notify_health_change(backend, old_health, new_health)
            except Exception as exc:
                _log.warning(
                    "health telegram notify failed backend=%s: %s",
                    backend,
                    type(exc).__name__,
                )
        try:
            import backend_reputation

            backend_reputation.record_failure_class(backend, error_class)
        except ImportError:
            pass
        except Exception as exc:
            _log.debug(
                "backend_reputation record failed backend=%s: %s",
                backend,
                type(exc).__name__,
            )

    # Update backend profile (outside lock to avoid deadlock)
    try:
        import backend_profile
        backend_profile.record_request(backend, 0.0, success=False)
    except ImportError:
        pass

    # Check retirement
    try:
        import backend_retirement
        action = backend_retirement.check_retirement(backend)
        if action:
            backend_retirement.apply_retirement(action)
    except ImportError:
        pass


def record_response_quality(
    backend: str,
    response_length: int,
    is_error_msg: bool = False,
) -> None:
    with _lock:
        quality = _quality_states.setdefault(backend, QualityState())
        quality.response_lengths.append(response_length)
        if response_length == 0:
            quality.empty_count += 1
        else:
            quality.empty_count = 0
        if is_error_msg:
            quality.error_msg_count += 1
