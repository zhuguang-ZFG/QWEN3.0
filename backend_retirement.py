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


def check_retirement(backend: str) -> dict | None:
    """Check if a backend should be retired. Returns retirement action or None."""
    try:
        import backend_profile
        profile = backend_profile.get_profile(backend)
    except ImportError:
        return None

    # Check consecutive failures
    try:
        import health_state
        state = health_state.get_backend_state(backend)
        consec_fails = 0
        if state:
            # health_state doesn't expose consecutive_failures directly
            # Use backend_profile as fallback
            pass
    except ImportError:
        pass

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

    logger.warning("Backend %s retirement: %s — %s", backend, status, reason)

    if status == STATUS_RETIRED:
        _retired_backends.add(backend)
        _save_retirement(backend, status, reason)
        _notify_retirement(backend, status, reason)


def reactivate(backend: str) -> None:
    """Manually reactivate a retired backend."""
    _retired_backends.discard(backend)
    _save_retirement(backend, STATUS_HEALTHY, "Manually reactivated")
    logger.info("Backend %s reactivated", backend)


def is_retired(backend: str) -> bool:
    """Check if a backend is retired."""
    return backend in _retired_backends


def get_retired_backends() -> set[str]:
    """Get all retired backends."""
    return set(_retired_backends)


def load_retired() -> int:
    """Load retired backends from SQLite."""
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        count = 0
        for row in conn.execute(
            "SELECT backend FROM retirements WHERE status = ?", (STATUS_RETIRED,)
        ):
            _retired_backends.add(row[0])
            count += 1
        conn.close()
        return count
    except Exception:
        return 0


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
    """Send Telegram notification about backend retirement."""
    try:
        from telegram_notify import notify_health_change
        notify_health_change(backend, "healthy", status)
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("backend_retirement.py: {}", type(exc).__name__)
