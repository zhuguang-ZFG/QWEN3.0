# DEPRECATED v3.0 — coding capability retired
"""Topology-aware eval routing for Windows local-proxy backends (P2-25).

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but eval topology routing is permanently disabled.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

DEFAULT_FRP_ROUTER = "http://127.0.0.1:8088"


def eval_via_router_enabled() -> bool:
    """DEPRECATED — always returns False."""
    return False


def eval_via_router_url() -> str:
    """DEPRECATED — returns empty string."""
    return ""


def _auto_frp_router_available() -> bool:
    """DEPRECATED — always returns False."""
    return False


def needs_via_router(backend: str) -> bool:
    """DEPRECATED — always returns False."""
    return False


def eval_api_key() -> str:
    """DEPRECATED — returns empty string."""
    return ""


def call_via_router(
    backend: str,
    messages: list[dict],
    max_tokens: int,
    *,
    router_url: str = "",
    timeout: float = 120.0,
) -> str:
    """DEPRECATED — raises OSError indicating eval capability retired."""
    raise OSError("eval capability retired")


def topology_status_lines() -> list[str]:
    """DEPRECATED — returns minimal status indicating eval topology is retired."""
    return ["eval_via_router=0"]
