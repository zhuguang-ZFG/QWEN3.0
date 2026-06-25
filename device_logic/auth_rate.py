"""Registration/login rate limits for device app auth (L2)."""

from __future__ import annotations

from config import settings

from rate_limiter import check_keyed_rate_limit

_DEFAULTS = {
    "register": 5,
    "login": 20,
    "sms": 10,
    "key_create": 10,
}

_LIMIT_ATTRS = {
    "register": "auth_register_per_min",
    "login": "auth_login_per_min",
    "sms": "auth_sms_per_min",
    "key_create": "auth_key_create_per_min",
}


def _limit_per_minute(action: str) -> int:
    value = getattr(settings.DEVICE, _LIMIT_ATTRS.get(action, ""), None)
    if isinstance(value, int) and value > 0:
        return value
    return _DEFAULTS.get(action, 10)


def allow_device_auth(action: str, client_ip: str) -> bool:
    """Return True when the client IP is within the per-action sliding window."""
    ip = (client_ip or "unknown").strip() or "unknown"
    return check_keyed_rate_limit(
        f"device_auth:{action}:{ip}",
        max_per_window=_limit_per_minute(action),
    )
