"""Passive health recording (CQ-014 slice 9)."""

from __future__ import annotations

import logging
import time
from typing import Optional

from health_models import (
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
from health_state import save_on_change

_log = logging.getLogger(__name__)


# ─── Failure classification (inlined from health_failure_classifier) ──────────

_TEXT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("anonymous_usage_exceeded",), "manual_refresh_required"),
    (("unauthorized", "forbidden", "invalid token", "invalid api key", "not authenticated"), "auth_expired"),
    (("too many requests", "rate limit", "rate exceeded", "slow down"), "rate_limited"),
    (("quota", "usage exhausted", "limit exceeded", "billing", "insufficient_quota"), "quota_exhausted"),
    (
        (
            "connection refused",
            "connection reset",
            "connection aborted",
            "name or service not known",
            "no route to host",
            "connection timed out",
            "timed out",
            "read timed out",
            "could not resolve host",
            "temporary failure in name resolution",
            "network is unreachable",
            "connectionerror",
            "remote end closed",
        ),
        "network_error",
    ),
    (
        (
            "jsondecodeerror",
            "expecting value",
            "unterminated string",
            "unexpected token",
            "invalid json",
            "syntax error",
            "expected",
            "malformed",
            "parse error",
        ),
        "malformed_response",
    ),
]

_CODE_RULES: list[tuple[set[int], str]] = [
    ({401, 403}, "auth_expired"),
    ({429}, "rate_limited"),
    ({502, 503, 504}, "network_error"),
    ({400}, "malformed_response"),
]


def _match_text_rule(lowered: str) -> str | None:
    """Find the first matching text-based classification rule."""
    for markers, classification in _TEXT_RULES:
        if any(m in lowered for m in markers):
            return classification
    return None


def _classify_timeout(lowered: str, error_code: int | None) -> str:
    """Handle timeout vs network-error disambiguation."""
    if any(m in lowered for m in ("timeout", "timed out")) and error_code != 408:
        if any(m in lowered for m in ("read timed", "connect timed", "connection timed")):
            return "network_error"
        return "timeout"
    return ""


def classify_failure(error_code: Optional[int] = None, error_text: str = "") -> str:
    lowered = (error_text or "").lower()
    result = _match_text_rule(lowered)
    if result:
        return result
    result = _classify_timeout(lowered, error_code)
    if result:
        return result
    for codes, classification in _CODE_RULES:
        if error_code in codes:
            return classification
    if error_code is not None and 500 <= error_code <= 599:
        return "provider_error"
    return "unknown_error"


# ─── Recording helpers ────────────────────────────────────────────────────────


def record_success(backend: str, latency_ms: float) -> None:
    should_persist = False
    with _lock:
        old_health = _health_map.get(backend)
        _health_map[backend] = "healthy"

        state = _cooldown_states.get(backend)
        if state:
            should_persist = True
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
        should_persist = should_persist or old_health != "healthy"

    if should_persist:
        save_on_change()

    # Update backend profile (outside lock to avoid deadlock)
    try:
        import backend_profile

        backend_profile.record_request(backend, latency_ms, success=True)
    except ImportError as exc:
        _log.warning("backend_profile not installed; success profile not recorded: %s", exc)


def _apply_cooldown(state: "CooldownState", error_code: int | None, error_class: str) -> None:
    """Apply cooldown and error class to the cooldown state."""
    if error_class not in ("rate_limited", "quota_exhausted"):
        state.consecutive_failures += 1
    state.last_error_code = error_code
    state.state = error_class
    state.last_error_class = error_class
    if error_class in ("auth_expired", "manual_refresh_required", "quota_exhausted"):
        state.current_cooldown = COOLDOWN_AUTH_FIXED
    elif error_class == "rate_limited":
        state.current_cooldown = calc_cooldown(state.consecutive_failures, 429)
    else:
        state.current_cooldown = calc_cooldown(state.consecutive_failures, error_code)
    state.cooldown_until = time.monotonic() + state.current_cooldown


def _update_health_map(backend: str, error_class: str, consecutive_failures: int) -> None:
    """Update the health map based on error class and failure count."""
    if error_class in ("auth_expired", "manual_refresh_required"):
        _health_map[backend] = "suspicious"
    elif error_class in ("rate_limited", "quota_exhausted"):
        _health_map[backend] = "degraded"
    elif consecutive_failures >= FAILURE_THRESHOLD_MIN_REQUESTS:
        _health_map[backend] = "dead"
    else:
        _health_map[backend] = "degraded"


def _post_failure_hooks(backend: str, error_class: str) -> None:
    """Run post-recording side effects (reputation, profile, retirement)."""
    try:
        import backend_reputation

        backend_reputation.record_failure_class(backend, error_class)
    except ImportError as exc:
        _log.warning("backend_reputation not installed; failure reputation not recorded: %s", exc)
    except Exception as exc:
        _log.warning("backend_reputation record failed backend=%s: %s", backend, exc, exc_info=True)
    try:
        import backend_profile

        backend_profile.record_request(backend, 0.0, success=False)
    except ImportError as exc:
        _log.warning("backend_profile not installed; failure profile not recorded: %s", exc)
    try:
        import backend_retirement

        action = backend_retirement.check_retirement(backend)
        if action:
            backend_retirement.apply_retirement(action)
    except ImportError as exc:
        _log.warning("backend_retirement not installed; retirement check skipped: %s", exc)


def record_failure(
    backend: str,
    error_code: Optional[int] = None,
    error_text: str = "",
) -> None:
    should_persist = False
    error_class = ""
    with _lock:
        if error_code == 400:
            state = _cooldown_states.setdefault(backend, CooldownState())
            state.bad_request_count = getattr(state, "bad_request_count", 0) + 1  # type: ignore[attr-defined]
            return

        state = _cooldown_states.setdefault(backend, CooldownState())
        error_class = classify_failure(error_code, error_text)
        _apply_cooldown(state, error_code, error_class)

        quality = _quality_states.setdefault(backend, QualityState())
        quality.last_failure = time.monotonic()
        quality.total_requests += 1
        quality.latencies.append(LATENCY_PENALTY)

        old_health = _health_map.get(backend, "healthy")
        _update_health_map(backend, error_class, state.consecutive_failures)
        new_health = _health_map[backend]
        should_persist = True
        if old_health != new_health:
            _log.info("backend health changed backend=%s old=%s new=%s", backend, old_health, new_health)

    # Run side effects outside the lock to avoid potential deadlocks with
    # backend_reputation / backend_profile / backend_retirement.
    _post_failure_hooks(backend, error_class)

    if should_persist:
        save_on_change()


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
