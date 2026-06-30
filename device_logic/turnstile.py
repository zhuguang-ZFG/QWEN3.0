"""Cloudflare Turnstile server-side verification for device-app auth."""

from __future__ import annotations

import logging
import os

import httpx

_log = logging.getLogger(__name__)

TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Warn loudly when the frontend widget is configured but server-side verification is not.
# This avoids a silent fail-open where Turnstile appears active but every request bypasses it.
if TURNSTILE_SITE_KEY and not TURNSTILE_SECRET_KEY:
    _log.warning(
        "TURNSTILE_SITE_KEY is set but TURNSTILE_SECRET_KEY is empty — "
        "Turnstile verification is DISABLED (fail-open misconfiguration)"
    )


def is_turnstile_configured() -> bool:
    """Return True when a Turnstile secret key is present."""
    return bool(TURNSTILE_SECRET_KEY)


async def verify_turnstile_token(token: str | None, remoteip: str | None = None) -> bool:
    """Verify a Turnstile response token with Cloudflare.

    Returns False when Turnstile is not configured, the token is missing, or the
    verification request fails. This keeps the auth flow safe-by-default.
    """
    if not is_turnstile_configured():
        return False
    if not token:
        return False
    data = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if remoteip:
        data["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(TURNSTILE_VERIFY_URL, data=data)
            response.raise_for_status()
            result = response.json()
    except Exception as exc:  # pragma: no cover - network errors logged only
        _log.warning("Turnstile verification request failed: %s", exc)
        return False

    if not result.get("success"):
        error_codes = result.get("error-codes", [])
        _log.warning("Turnstile verification rejected: %s", error_codes)
        return False
    return True
