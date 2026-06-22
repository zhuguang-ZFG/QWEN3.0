"""Route-level rate-limit helpers built on the shared limiter modules."""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

import rate_limiter
from routes.request_tracking import client_ip


def _disabled() -> bool:
    return os.environ.get("LIMA_RATE_LIMIT_DISABLE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def check_key_limit(
    key: str,
    default_max: int,
    *,
    window: float = 60.0,
) -> JSONResponse | None:
    """Return a 429 JSONResponse when the arbitrary key exceeds the sliding-window limit."""
    if _disabled():
        return None
    if not rate_limiter.check_keyed_rate_limit(key, max_per_window=default_max, window=window):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
        )
    return None


def check_ip_limit(
    request: Request,
    scope: str,
    default_max: int,
    *,
    window: float = 60.0,
) -> JSONResponse | None:
    """Return a 429 JSONResponse when the client's IP exceeds the sliding-window limit."""
    if _disabled():
        return None
    key = f"{scope}:{client_ip(request)}"
    if not rate_limiter.check_keyed_rate_limit(key, max_per_window=default_max, window=window):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}},
        )
    return None
