"""Backend Retirement — automatic degradation and removal of failing backends.

Monitors backend health and automatically retires backends that consistently fail.
Retired backends are removed from routing pools to save fallback time.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time

logger = logging.getLogger(__name__)
_log = logger

DB_PATH = os.environ.get("LIMA_BACKEND_RETIREMENT_DB", "data/backend_retirement.db")

# Retirement thresholds
CONSECUTIVE_FAILURES_DEGRADED = 10
SUCCESS_RATE_SUSPICIOUS_24H = 0.20
SUCCESS_RATE_RETIRING_7D = 0.10
SUCCESS_RATE_RETIRED_30D = 0.05

# Status labels
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_SUSPICIOUS = "suspicious"
STATUS_RETIRING = "retiring"
STATUS_RETIRED = "retired"

# Runtime overrides: backends removed from routing pools
_retired_backends: set[str] = set()
_RELOAD_INTERVAL_SEC = float(os.environ.get("LIMA_BACKEND_RETIREMENT_RELOAD_SEC", "300"))
_last_reload_ts: float = time.time()


def _maybe_reload_retired() -> None:
    """Refresh in-memory retired set from SQLite (multi-worker sync)."""
    global _last_reload_ts
    now_ts = time.time()
    if now_ts - _last_reload_ts < _RELOAD_INTERVAL_SEC:
        return
    _last_reload_ts = now_ts
    _retired_backends.clear()
    load_retired()


def _mark_health_retired(backend: str) -> None:
    """Reflect persisted retirement in runtime health state."""
    try:
        import health_state
    except ImportError as exc:
        logger.warning("health_state unavailable; retired backend not marked: %s", exc)
        return
    except Exception as exc:
        logger.warning(
            "Failed to import health_state for retired backend=%s: %s",
            backend,
            type(exc).__name__,
        )
        return

    try:
        with health_state._lock:
            current = health_state._health_map.get(backend)
            if current != STATUS_HEALTHY:
                health_state._health_map[backend] = "dead"
            state = health_state._cooldown_states.setdefault(backend, health_state.CooldownState())
            state.state = STATUS_RETIRED
            state.last_error_class = STATUS_RETIRED
            state.last_error_code = None
    except Exception as exc:
        logger.warning(
            "Failed to mark retired backend health backend=%s: %s",
            backend,
            type(exc).__name__,
        )


def check_retirement(backend: str) -> dict | None:
    """Check if a backend should be retired. Returns retirement action or None."""
    try:
        import backend_profile

        profile = backend_profile.get_profile(backend)
    except ImportError as exc:
        logger.warning("backend_profile unavailable; cannot evaluate backend retirement: %s", exc)
        return None

    total = profile.successes + profile.failures
    if total < 5:
        return None  # Not enough data

    # Check success rates over different windows
    recent_success_rate = profile.success_rate

    if recent_success_rate < SUCCESS_RATE_RETIRED_30D and total >= 20:
        return {
            "action": "retire",
            "backend": backend,
            "reason": f"Success rate {recent_success_rate:.1%} over {total} requests (threshold: {SUCCESS_RATE_RETIRED_30D:.0%})",
            "status": STATUS_RETIRED,
        }

    if recent_success_rate < SUCCESS_RATE_RETIRING_7D and total >= 10:
        return {
            "action": "degrade",
            "backend": backend,
            "reason": f"Success rate {recent_success_rate:.1%} over {total} requests (threshold: {SUCCESS_RATE_RETIRING_7D:.0%})",
            "status": STATUS_RETIRING,
        }

    if recent_success_rate < SUCCESS_RATE_SUSPICIOUS_24H and total >= 5:
        return {
            "action": "suspend",
            "backend": backend,
            "reason": f"Success rate {recent_success_rate:.1%} over {total} requests (threshold: {SUCCESS_RATE_SUSPICIOUS_24H:.0%})",
            "status": STATUS_SUSPICIOUS,
        }

    return None


def apply_retirement(action: dict) -> None:
    """Apply a retirement action to a backend."""
    backend = action["backend"]
    status = action["status"]
    reason = action["reason"]

    if status == STATUS_RETIRED and backend in _retired_backends:
        _mark_health_retired(backend)
        return

    logger.warning("Backend %s retirement: %s — %s", backend, status, reason)

    if status == STATUS_RETIRED:
        _retired_backends.add(backend)
        _mark_health_retired(backend)
        _save_retirement(backend, status, reason)
        _notify_retirement(backend, status, reason)
        _record_retirement_metric(backend)


def reactivate(backend: str) -> None:
    """Manually reactivate a retired backend."""
    _retired_backends.discard(backend)
    _save_retirement(backend, STATUS_HEALTHY, "Manually reactivated")
    try:
        import health_state

        health_state.clear_cooldown(backend)
        with health_state._lock:
            health_state._health_map[backend] = STATUS_HEALTHY
    except ImportError as exc:
        logger.warning("health_state unavailable; reactivated backend not marked: %s", exc)
    except Exception as exc:
        logger.warning(
            "Failed to mark reactivated backend health backend=%s: %s",
            backend,
            type(exc).__name__,
        )
    logger.info("Backend %s reactivated", backend)


def is_retired(backend: str) -> bool:
    """Check if a backend is retired."""
    _maybe_reload_retired()
    return backend in _retired_backends


def get_retired_backends() -> set[str]:
    """Get all retired backends."""
    _maybe_reload_retired()
    return set(_retired_backends)


def load_retired() -> int:
    """Load retired backends from SQLite."""
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        count = 0
        for row in conn.execute("SELECT backend FROM retirements WHERE status = ?", (STATUS_RETIRED,)):
            _retired_backends.add(row[0])
            _mark_health_retired(row[0])
            count += 1
        conn.close()
        return count
    except Exception as exc:
        logger.warning("Failed to load retired backends: %s", type(exc).__name__)
        return 0


def get_recovery_snapshot(
    *, dead_backends: list[str] | None = None, degraded_backends: list[str] | None = None
) -> dict:
    """Return operator-facing recovery state without reactivating providers."""
    retired = sorted(_retired_backends)
    dead = sorted(set(dead_backends or []))
    degraded = sorted(set(degraded_backends or []))
    candidates = sorted((set(dead) | set(degraded)) - set(retired))
    return {
        "retired_count": len(retired),
        "retired_list": retired[:20],
        "probe_candidates": candidates[:20],
        "manual_reactivation": "probe first, then call backend_retirement.reactivate(backend) after fresh success evidence",
    }


def _save_retirement(backend: str, status: str, reason: str) -> None:
    """Save retirement record to SQLite."""
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retirements (
                backend TEXT PRIMARY KEY,
                status TEXT,
                reason TEXT,
                retired_at REAL
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO retirements VALUES (?, ?, ?, ?)",
            (backend, status, reason, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Failed to save retirement: %s", exc)


def _notify_retirement(backend: str, status: str, reason: str) -> None:
    """Record backend retirement notification locally."""
    _log.warning(
        "backend retired backend=%s status=%s reason=%s",
        backend,
        status,
        reason[:200],
    )


def _record_retirement_metric(backend: str) -> None:
    try:
        from observability import prometheus_metrics

        prometheus_metrics.record_backend_retirement_event(backend)
    except Exception as exc:
        logger.warning("Prometheus retirement metric skipped backend=%s: %s", backend, type(exc).__name__)
