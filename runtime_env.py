"""Runtime environment helpers."""

from __future__ import annotations

import os

from config import settings

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def is_production_runtime() -> bool:
    """Prefer live ``LIMA_RUNTIME_ENV``; fall back to import-time FLAGS."""
    raw = os.environ.get("LIMA_RUNTIME_ENV", "").strip().lower()
    if not raw:
        raw = (settings.FLAGS.runtime_env or "").strip().lower()
    return raw in {"prod", "production"}


def jwt_require_typ() -> bool:
    """Reject JWTs missing ``typ`` when env says so; production defaults to on."""
    raw = os.environ.get("LIMA_JWT_REQUIRE_TYP", "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return is_production_runtime()


def rate_limit_disabled() -> bool:
    """Whether rate limiting is off. Production always enforces limits."""
    if is_production_runtime():
        return False
    raw = os.environ.get("LIMA_RATE_LIMIT_DISABLE", "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return bool(settings.SECURITY.rate_limit_disable)
