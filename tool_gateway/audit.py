import time


def audit_event(event_type: str, **kwargs) -> dict:
    return {
        "time": int(time.time()),
        "event": event_type,
        **kwargs,
    }
