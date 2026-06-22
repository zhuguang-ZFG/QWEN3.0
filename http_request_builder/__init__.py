"""HTTP client factory and request builders (CQ-014 slice 8)."""

from __future__ import annotations

from .body import _build_body
from .client import GFW_PROXY_URL, GFW_USER_AGENT, _build_async_client, _build_client
from .headers import (
    _build_headers,
    _has_key,
    _key_pool_provider,
    _report_key_result,
    _select_key,
)

__all__ = [
    "GFW_PROXY_URL",
    "GFW_USER_AGENT",
    "_build_async_client",
    "_build_body",
    "_build_client",
    "_build_headers",
    "_has_key",
    "_key_pool_provider",
    "_report_key_result",
    "_select_key",
]
