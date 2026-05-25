"""Legacy circuit breaker used by smart_router backend calls (CQ-014 slice 6)."""

from __future__ import annotations

import os
import sys
import threading
import time

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"

_cb_lock = threading.Lock()
_cb_state: dict[str, dict] = {}

CB_FAILURE_THRESHOLD = 3
CB_RECOVERY_TIMEOUT = 60
CB_SUCCESS_THRESHOLD = 2


def _cb_get(name: str) -> dict:
    with _cb_lock:
        if name not in _cb_state:
            _cb_state[name] = {
                "state": "closed",
                "failures": 0,
                "successes": 0,
                "opened_at": 0,
                "total_calls": 0,
                "total_errors": 0,
                "total_latency_ms": 0,
            }
        return dict(_cb_state[name])


def cb_allow(name: str) -> bool:
    """Return True when backend calls are allowed."""
    state = _cb_get(name)
    if state["state"] == "closed":
        return True
    if state["state"] == "open":
        if time.time() - state["opened_at"] > CB_RECOVERY_TIMEOUT:
            with _cb_lock:
                _cb_state[name]["state"] = "half-open"
                _cb_state[name]["successes"] = 0
            return True
        return False
    return True


def cb_record(name: str, success: bool, latency_ms: int = 0) -> None:
    """Record backend call outcome and update breaker state."""
    with _cb_lock:
        state = _cb_state.setdefault(
            name,
            {
                "state": "closed",
                "failures": 0,
                "successes": 0,
                "opened_at": 0,
                "total_calls": 0,
                "total_errors": 0,
                "total_latency_ms": 0,
            },
        )
        state["total_calls"] += 1
        state["total_latency_ms"] += latency_ms
        if success:
            if state["state"] == "half-open":
                state["successes"] += 1
                if state["successes"] >= CB_SUCCESS_THRESHOLD:
                    state["state"] = "closed"
                    state["failures"] = 0
                    if DEBUG:
                        print(f"[CB] {name}: half-open -> closed", file=sys.stderr)
            else:
                state["failures"] = 0
        else:
            state["total_errors"] += 1
            state["failures"] += 1
            if state["state"] in ("closed", "half-open") and state["failures"] >= CB_FAILURE_THRESHOLD:
                state["state"] = "open"
                state["opened_at"] = time.time()
                print(
                    f'[CB] {name}: OPEN (circuit breaker tripped after {state["failures"]} failures)',
                    file=sys.stderr,
                )


def cb_status() -> dict:
    """Return breaker summary for all backends."""
    result = {}
    with _cb_lock:
        for name, state in _cb_state.items():
            total = state["total_calls"]
            err_rate = state["total_errors"] / total if total > 0 else 0
            avg_lat = state["total_latency_ms"] / total if total > 0 else 0
            result[name] = {
                "state": state["state"],
                "failures": state["failures"],
                "error_rate": f"{err_rate:.1%}",
                "avg_latency_ms": int(avg_lat),
                "total_calls": total,
            }
    return result


def reset_for_tests() -> None:
    """Clear breaker state (tests only)."""
    with _cb_lock:
        _cb_state.clear()
