"""Telemetry-driven routing guardrails for unstable backends."""

from __future__ import annotations

import os
import time
from typing import Any

HARD_FAILURE_CLASSES = {
    "timeout",
    "admission_blocked",
    "empty_response",
    "provider_5xx",
    "network",
    "quota",
    "auth",
}


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _short(value: Any, limit: int = 80) -> str:
    text = str(value or "")
    return text[:limit]


def _recent_records(limit: int) -> list[dict[str, Any]]:
    try:
        from observability.backend_telemetry import recent_backend_attempts

        records = recent_backend_attempts(limit=limit)
    except ImportError:
        return []
    return [item for item in records if isinstance(item, dict)]


def _decision_multiplier(failures: int, attempts: int) -> float:
    if attempts <= 0 or failures <= 0:
        return 1.0
    failure_ratio = min(1.0, failures / max(attempts, 1))
    return round(max(0.25, 1.0 - failure_ratio * 0.75), 3)


def backend_guard_snapshot(
    *,
    limit: int = 500,
    now: float | None = None,
) -> dict[str, Any]:
    """Return short-lived backend quarantine and penalty decisions.

    Decisions are derived from recent sanitized telemetry only. They are
    intentionally non-persistent: a newer success clears quarantine, while
    residual failure ratio still down-ranks the backend for a short window.
    """
    enabled = _env_bool("LIMA_ROUTING_GUARD_ENABLED", True)
    window_sec = _env_int("LIMA_ROUTING_GUARD_WINDOW_SEC", 600)
    quarantine_sec = _env_int("LIMA_ROUTING_GUARD_QUARANTINE_SEC", 180)
    repeated_threshold = _env_int("LIMA_ROUTING_GUARD_FAILURE_THRESHOLD", 3)
    current = time.time() if now is None else now

    snapshot: dict[str, Any] = {
        "enabled": enabled,
        "window_sec": window_sec,
        "quarantine_sec": quarantine_sec,
        "failure_threshold": repeated_threshold,
        "hard_error_classes": sorted(HARD_FAILURE_CLASSES),
        "decisions": {},
    }
    if not enabled:
        return snapshot

    records = [
        item for item in _recent_records(limit)
        if current - float(item.get("ts", 0) or 0) <= window_sec
    ]
    per_backend: dict[str, dict[str, Any]] = {}
    for order, item in enumerate(records):
        backend = _short(item.get("backend"), 80) or "unknown"
        stats = per_backend.setdefault(
            backend,
            {
                "attempts": 0,
                "success": 0,
                "failures": 0,
                "hard_failures": 0,
                "latest_success_ts": 0.0,
                "latest_success_order": -1,
                "latest_failure_ts": 0.0,
                "latest_failure_order": -1,
                "latest_failure_class": "",
            },
        )
        ts = float(item.get("ts", 0) or 0)
        error_class = _short(item.get("error_class"), 40)
        success = bool(item.get("success", False))
        stats["attempts"] += 1
        if success:
            stats["success"] += 1
            if (ts, order) > (
                float(stats["latest_success_ts"]),
                int(stats["latest_success_order"]),
            ):
                stats["latest_success_ts"] = ts
                stats["latest_success_order"] = order
        else:
            stats["failures"] += 1
            if (ts, order) > (
                float(stats["latest_failure_ts"]),
                int(stats["latest_failure_order"]),
            ):
                stats["latest_failure_ts"] = ts
                stats["latest_failure_order"] = order
                stats["latest_failure_class"] = error_class
            if error_class in HARD_FAILURE_CLASSES:
                stats["hard_failures"] += 1

    decisions: dict[str, dict[str, Any]] = {}
    for backend, stats in per_backend.items():
        failures = int(stats["failures"])
        attempts = int(stats["attempts"])
        latest_failure_ts = float(stats["latest_failure_ts"])
        latest_success_ts = float(stats["latest_success_ts"])
        latest_failure_order = int(stats["latest_failure_order"])
        latest_success_order = int(stats["latest_success_order"])
        latest_error = _short(stats["latest_failure_class"], 40)
        latest_failure_age = int(max(0.0, current - latest_failure_ts)) if latest_failure_ts else 0
        failure_after_success = (
            latest_failure_ts,
            latest_failure_order,
        ) > (
            latest_success_ts,
            latest_success_order,
        )

        status = "healthy"
        reason = ""
        multiplier = _decision_multiplier(failures, attempts)
        if (
            failure_after_success
            and latest_error in HARD_FAILURE_CLASSES
            and latest_failure_age <= quarantine_sec
        ):
            status = "quarantined"
            reason = "recent_hard_failure"
            multiplier = 0.05
        elif (
            failure_after_success
            and failures >= repeated_threshold
            and latest_failure_age <= quarantine_sec
        ):
            status = "quarantined"
            reason = "repeated_recent_failures"
            multiplier = 0.05
        elif failures:
            status = "penalized"
            reason = "recent_failure_ratio"

        if status != "healthy":
            decisions[backend] = {
                "status": status,
                "reason": reason,
                "attempts": attempts,
                "success": int(stats["success"]),
                "failures": failures,
                "hard_failures": int(stats["hard_failures"]),
                "last_error_class": latest_error,
                "last_failure_age_sec": latest_failure_age,
                "penalty_multiplier": multiplier,
            }

    snapshot["decisions"] = decisions
    return snapshot


def backend_decision(backend: str) -> dict[str, Any]:
    return backend_guard_snapshot()["decisions"].get(backend, {})


def is_backend_quarantined(backend: str) -> bool:
    return backend_decision(backend).get("status") == "quarantined"


def penalty_multiplier(backend: str) -> float:
    decision = backend_decision(backend)
    value = decision.get("penalty_multiplier", 1.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0
