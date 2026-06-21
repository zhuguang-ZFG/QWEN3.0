"""device_sn format validation (L1)."""

from __future__ import annotations

import re

from device_logic.errors import DeviceLogicError

# Alphanumeric first char; then letters, digits, MAC/colon/hyphen/underscore/dot (3–64 total).
_DEVICE_SN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{2,63}$")


def validate_device_sn(device_sn: str) -> str:
    """Return normalized serial or raise DeviceLogicError(4002)."""
    normalized = (device_sn or "").strip()
    if not normalized or not _DEVICE_SN_RE.fullmatch(normalized):
        raise DeviceLogicError(4002, "invalid deviceSn format", 400)
    return normalized
