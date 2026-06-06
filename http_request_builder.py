"""HTTP client factory and request builders (CQ-014 slice 8)."""

from __future__ import annotations

import logging
import os
import threading
import time as _time

import httpx

from backends import GFW_BACKENDS
from http_body_builder import build_body as _build_body_impl

# Re-export extracted functions for backward compatibility
from http_key_selector import (
    has_key,
    key_pool_provider,
    report_key_result,
    select_key,
)

# Backward-compat aliases (callers use underscore-prefixed names)
_key_pool_provider = key_pool_provider
_select_key = select_key
_has_key = has_key
_report_key_result = report_key_result

logger = logging.getLogger(__name__)

GFW_PROXY_URL = os.environ.get("GFW_PROXY", "http://127.0.0.1:7897")
GFW_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── Connection pool per backend — reused across requests to eliminate TCP/TLS handshake ──
_async_client_pool: dict[str, httpx.AsyncClient] = {}
_sync_client_pool: dict[str, httpx.Client] = {}
_sync_pool_lock = threading.Lock()
_POOL_MAX_KEEPALIVE = 5
_POOL_MAX_CONNECTIONS = 20
_POOL_RECYCLE_SECONDS = 300


def _build_client(backend: str, timeout: float) -> httpx.Client:
    """Create a new httpx.Client (not pooled). Kept for backward compat."""
    if backend in GFW_BACKENDS:
        return httpx.Client(
            proxy=GFW_PROXY_URL,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))


def _build_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient (not pooled). Kept for backward compat."""
    if backend in GFW_BACKENDS:
        return httpx.AsyncClient(
            proxy=GFW_PROXY_URL,
            headers={"User-Agent": GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))


def _get_client(backend: str, timeout: float) -> httpx.Client:
    """Get a pooled httpx.Client — reuses connections across requests.

    Thread-safe via _sync_pool_lock. Timeout is included in the pool key
    so that callers with different timeout requirements get separate clients.
    Old pool entries are closed on eviction to avoid TCP/FD leaks.
    """
    key = f"{backend}:{int(timeout)}:{int(_time.time() // _POOL_RECYCLE_SECONDS)}"
    with _sync_pool_lock:
        if key not in _sync_client_pool:
            limits = httpx.Limits(
                max_keepalive_connections=_POOL_MAX_KEEPALIVE,
                max_connections=_POOL_MAX_CONNECTIONS)
            if backend in GFW_BACKENDS:
                client = httpx.Client(
                    proxy=GFW_PROXY_URL,
                    headers={"User-Agent": GFW_USER_AGENT},
                    timeout=httpx.Timeout(timeout, connect=10.0),
                    limits=limits)
            else:
                client = httpx.Client(
                    timeout=httpx.Timeout(timeout, connect=10.0),
                    limits=limits)
            # Clean up old pool entries for this backend
            stale = [k for k in _sync_client_pool if k.startswith(f"{backend}:")]
            for sk in stale[:-2]:
                old = _sync_client_pool.pop(sk, None)
                if old is not None:
                    try:
                        old.close()
                    except Exception as exc:
                        logger.debug("pool cleanup: close(%s) failed: %s", sk, type(exc).__name__)
            _sync_client_pool[key] = client
        return _sync_client_pool[key]


def _get_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    """Get a pooled httpx.AsyncClient — reuses connections across requests.

    Timeout is included in the pool key. Old pool entries are closed on eviction.
    No lock needed — asyncio event loop is single-threaded per context.
    """
    key = f"{backend}:{int(timeout)}:{int(_time.time() // _POOL_RECYCLE_SECONDS)}"
    if key not in _async_client_pool:
        limits = httpx.Limits(
            max_keepalive_connections=_POOL_MAX_KEEPALIVE,
            max_connections=_POOL_MAX_CONNECTIONS)
        if backend in GFW_BACKENDS:
            client = httpx.AsyncClient(
                proxy=GFW_PROXY_URL,
                headers={"User-Agent": GFW_USER_AGENT},
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=limits)
        else:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=limits)
        # Clean up old pool entries for this backend
        stale = [k for k in _async_client_pool if k.startswith(f"{backend}:")]
        for sk in stale[:-2]:
            old = _async_client_pool.pop(sk, None)
            if old is not None:
                try:
                    old.close()
                except Exception as exc:
                    logger.debug("pool cleanup: close(%s) failed: %s", sk, type(exc).__name__)
        _async_client_pool[key] = client
    return _async_client_pool[key]


def _build_headers(backend_cfg: dict, key: str | None = None) -> dict:
    fmt = backend_cfg["fmt"]
    auth_style = backend_cfg.get("auth", "x-api-key")
    key = backend_cfg["key"] if key is None else key

    # 支持后端自定义headers（如免费API需要User-Agent）
    custom_headers = backend_cfg.get("headers", {})

    if fmt == "anthropic":
        if auth_style == "bearer":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "anthropic-version": "2023-06-01",
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            }
    else:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "LiMa/2.0",
        }
    # 合并自定义headers（覆盖默认值）
    headers.update(custom_headers)
    return headers


def _build_headers_with_affinity(
    backend_cfg: dict,
    key: str | None = None,
    backend_name: str = "",
    session_id: str = "",
) -> dict:
    """Build headers with optional x-session-affinity (request.ts:181).

    Non-OpenCode providers get x-session-affinity for load balancer stickiness.
    """
    headers = _build_headers(backend_cfg, key)
    # M-OC21: x-session-affinity for non-opencode providers
    if session_id and backend_name:
        from provider_kind import detect_provider_kind
        pk = detect_provider_kind(backend_name, backend_cfg.get("model", ""))
        if pk not in ("opencode_zen",):
            headers["x-session-affinity"] = session_id
    return headers


def _build_body(
    backend_cfg: dict, messages: list[dict], max_tokens: int,
    system_prompt: str = "", ide: str = "", stream: bool = False,
    tools: list[dict] | None = None, reasoning_effort: str | None = None,
    backend_name: str = "",
) -> bytes:
    return _build_body_impl(
        backend_cfg, messages, max_tokens,
        system_prompt=system_prompt, ide=ide, stream=stream,
        tools=tools, reasoning_effort=reasoning_effort,
        backend_name=backend_name,
    )

