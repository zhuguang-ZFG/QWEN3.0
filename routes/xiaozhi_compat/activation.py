"""Activation code state machine for XiaoZhi v1 device pairing."""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from typing import Any

_log = logging.getLogger(__name__)

ACTIVATION_TTL_SECONDS = 600
_activation_codes: dict[str, dict[str, Any]] = {}
_activation_lock = threading.Lock()


def _expire_stale_codes(now_ts: float) -> None:
    """Remove activation codes that have exceeded their TTL."""
    with _activation_lock:
        for saved_code, data in list(_activation_codes.items()):
            if data["expires_at"] <= now_ts:
                _activation_codes.pop(saved_code, None)


def check_activation_code(code: str) -> bool:
    """Validate an activation code.

    In-memory generated codes take precedence. If none match and the
    environment pins a static code, compare against it. Otherwise reject.
    """
    now_ts = time.time()
    _expire_stale_codes(now_ts)
    with _activation_lock:
        saved = _activation_codes.get(code)
        if saved and saved["expires_at"] > now_ts:
            return True
    expected = os.environ.get("LIMA_XIAOZHI_ACTIVATION_CODE", "").strip()
    if expected:
        return secrets.compare_digest(code, expected)
    _log.warning("LIMA_XIAOZHI_ACTIVATION_CODE is not configured; rejecting unissued activation code")
    return False


def new_activation_code(mac_address: str = "") -> str:
    """Generate a new short-lived activation code."""
    now_ts = time.time()
    _expire_stale_codes(now_ts)
    with _activation_lock:
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in _activation_codes:
                break
        _activation_codes[code] = {
            "mac_address": mac_address,
            "expires_at": now_ts + ACTIVATION_TTL_SECONDS,
        }
        return code
