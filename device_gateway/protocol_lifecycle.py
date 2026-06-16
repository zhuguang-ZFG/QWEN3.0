"""Motion task lifecycle validation for device events."""

from __future__ import annotations

from typing import Any

from device_gateway.protocol_core import REQUIRED_MOTION_LIFECYCLE_PHASES, TERMINAL_MOTION_PHASES


def validate_motion_task_lifecycle(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that a motion task event sequence is well-formed.

    Returns {"ok": True, "terminal_phase": "done"} or
            {"ok": False, "reason": "...", "missing_phase": "..."}
    """
    if not events:
        return {"ok": False, "reason": "no events recorded", "missing_phase": "accepted"}
    phases = [e.get("phase", "") for e in events]
    terminal = next((p for p in phases if p in TERMINAL_MOTION_PHASES), None)
    if terminal is None:
        return {"ok": False, "reason": "no terminal phase reached", "missing_phase": "done|failed"}
    if terminal == "failed":
        error = None
        for e in reversed(events):
            err = e.get("error") if isinstance(e, dict) else None
            if isinstance(err, dict) and err.get("code"):
                error = err
                break
        if error is None:
            return {"ok": False, "reason": "failed event missing error code"}
        return {"ok": True, "terminal_phase": "failed", "error": error}
    return {"ok": True, "terminal_phase": terminal}
