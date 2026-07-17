"""Startup guards for dlc_mcp (keep server.py under size gate)."""

from __future__ import annotations

import logging
import sys
from urllib.parse import urlparse

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_log = logging.getLogger(__name__)


def is_remote_dlc_api(url: str) -> bool:
    """True when DLC_API_URL host is not loopback (requires DLC_API_TOKEN)."""
    host = (urlparse(url).hostname or "").lower()
    return host not in _LOOPBACK_HOSTS


def require_remote_api_token(*, api_url: str, api_token: str) -> None:
    if is_remote_dlc_api(api_url) and not api_token.strip():
        _log.error("DLC_API_TOKEN required when DLC_API_URL is non-loopback (%s)", api_url)
        sys.exit(1)
