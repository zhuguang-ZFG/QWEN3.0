"""Registration/login rate limits for device app auth (L2)."""

from __future__ import annotations

import os

from rate_limiter import check_keyed_rate_limit

_DEFAULTS = {
    "register": 5,
    "login": 20,
    "sms": 10,
}


def _limit_per_minute(action: str) -> int:
    env_name = {
        "register": "LIMA_DEVICE_AUTH_REGISTER_PER_MIN",
        "login": "LIMA_DEVICE_AUTH_LOGIN_PER_MIN",
        "sms": "LIMA_DEVICE_AUTH_SMS_PER_MIN",
    }[action]
    raw = os.environ.get(env_name, "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return _DEFAULTS[action]


def allow_device_auth(action: str, client_ip: str) -> bool:
    """Return True when the client IP is within the per-action sliding window."""
    ip = (client_ip or "unknown").strip() or "unknown"
    return check_keyed_rate_limit(
        f"device_auth:{action}:{ip}",
        max_per_window=_limit_per_minute(action),
    )
