"""Eval routing topology (M6: all backends cloud-native, no FRP/local proxies needed)."""

from __future__ import annotations

import os


def eval_via_router_enabled() -> bool:
    """M6: No local proxies remain. FRP eval routing is disabled."""
    return False


def eval_via_router_url() -> str:
    """M6: Always returns empty — no FRP router needed."""
    return ""


def needs_via_router(backend: str) -> bool:
    """M6: LOCAL_ONLY_BACKENDS is empty — never needs router."""
    return False


def eval_api_key() -> str:
    return os.environ.get("LIMA_API_KEY", "").strip()


def call_via_router(
    backend: str,
    messages: list[dict],
    max_tokens: int,
    *,
    router_url: str = "",
    timeout: float = 120.0,
) -> str:
    """M6: No local proxies — this should never be called."""
    raise OSError("M6: all backends are cloud-native, eval_via_router is obsolete")


def topology_status_lines() -> list[str]:
    return ["eval_via_router=0 (M6: all cloud-native)"]
