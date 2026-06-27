"""Startup state and phase recording for LiMa lifespan."""

from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)

STARTUP_PHASES: list[dict[str, Any]] = []

# Public startup state for /health and observability.
# status: "starting" | "ready" | "warming" | "error"
_startup_state: dict[str, Any] = {
    "status": "starting",
    "critical_done": False,
    "pending_warm": [],
    "errors": [],
}


def get_startup_state() -> dict[str, Any]:
    """Return a snapshot of the current startup state."""
    return {
        "status": _startup_state["status"],
        "critical_done": _startup_state["critical_done"],
        "pending_warm": list(_startup_state["pending_warm"]),
        "errors": list(_startup_state["errors"]),
    }


def set_startup_status(status: str) -> None:
    _startup_state["status"] = status
    _log.warning("[LIFESPAN] startup_status=%s", status)
    try:
        from observability.prometheus_metrics import record_startup_status

        record_startup_status(status)
    except ImportError:
        pass


def reset_startup_state() -> None:
    """Clear startup state before a new lifespan run."""
    _startup_state["status"] = "starting"
    _startup_state["critical_done"] = False
    _startup_state["pending_warm"].clear()
    _startup_state["errors"].clear()


def record_startup_error(label: str, exc: Exception) -> None:
    _startup_state["errors"].append(f"{label}: {exc}")


def add_pending_warm(name: str) -> None:
    _startup_state["pending_warm"].append(name)


def remove_pending_warm(name: str) -> None:
    if name in _startup_state["pending_warm"]:
        _startup_state["pending_warm"].remove(name)


def mark_critical_done() -> None:
    _startup_state["critical_done"] = True


def is_critical_done() -> bool:
    return bool(_startup_state["critical_done"])


def has_pending_warm() -> bool:
    return bool(_startup_state["pending_warm"])


def record_phase(name: str, elapsed_ms: float, status: str = "ok", detail: str = "") -> dict[str, Any]:
    phase = {
        "name": name,
        "elapsed_ms": round(elapsed_ms, 1),
        "status": status,
        "detail": detail,
    }
    STARTUP_PHASES.append(phase)
    _log.warning("[LIFESPAN] phase=%s elapsed_ms=%.1f status=%s %s", name, elapsed_ms, status, detail)
    try:
        from observability.prometheus_metrics import record_startup_phase

        record_startup_phase(name, elapsed_ms)
    except ImportError:
        pass
    return phase


class PhaseTimer:
    """Context manager that records elapsed time for a lifespan phase.

    Phases are appended to STARTUP_PHASES in start order so that critical
    and warm phases remain readable even when warm tasks run concurrently.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.started = 0.0
        self._phase: dict[str, Any] | None = None

    async def __aenter__(self):
        self.started = time.perf_counter()
        self._phase = record_phase(self.name, 0.0, "running", "")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        elapsed_ms = (time.perf_counter() - self.started) * 1000
        status = "error" if exc else "ok"
        detail = f"{exc}" if exc else ""
        if self._phase is not None:
            self._phase["elapsed_ms"] = round(elapsed_ms, 1)
            self._phase["status"] = status
            self._phase["detail"] = detail
        _log.warning("[LIFESPAN] phase=%s elapsed_ms=%.1f status=%s %s", self.name, elapsed_ms, status, detail)
