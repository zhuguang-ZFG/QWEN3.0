import time


def audit_event(tool: str, ok: bool, reason: str = "") -> dict:
    return {
        "time": int(time.time()),
        "tool": tool,
        "ok": ok,
        "reason": reason,
    }
