"""Backend attempt telemetry helpers for routing_executor."""

from __future__ import annotations

import logging
from typing import Optional

_log = logging.getLogger(__name__)


def extract_error_code(e: Exception) -> Optional[int]:
    """Best-effort extraction of an HTTP-like status code from an exception."""
    for attr in ("status_code", "code", "status"):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if "429" in s:
        return 429
    if "401" in s:
        return 401
    if "403" in s:
        return 403
    return None


def _record_backend_attempt(**kwargs) -> None:
    try:
        from observability.backend_telemetry import record_backend_attempt

        record_backend_attempt(**kwargs)
    except ImportError:
        _log.debug("observability.backend_telemetry not installed; backend telemetry skipped")
