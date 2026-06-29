"""HTTP client factory helpers.

AUDIT-8-P4: clients are cached per backend (proxy/timeout/trust_env are all
backend-determined) and reused across requests to avoid rebuilding the
connection pool + TLS handshake on every call. Cached clients are wrapped in a
no-op context manager so existing `with _build_client(...) as client:` call
sites keep working without closing the shared client.
"""

from __future__ import annotations

import logging
import threading
from typing import Literal

import httpx

from backends_constants import GFW_BACKENDS
from backends_registry import BACKENDS
from config import settings

_log = logging.getLogger(__name__)

GFW_PROXY_URL = settings.EMBEDDING.gfw_proxy or "http://127.0.0.1:7897"
GFW_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Connection-pool limits per cached client (mirrors deploy/jdcloud worker).
_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=5)

_CLIENT_CACHE: dict[str, httpx.Client] = {}
_ASYNC_CLIENT_CACHE: dict[str, httpx.AsyncClient] = {}
_CACHE_LOCK = threading.RLock()


def _needs_proxy(url: str) -> bool:
    """Check if a URL should use the outbound proxy (skip local URLs)."""
    local_hosts = ("127.0.0.1", "localhost", "0.0.0.0")
    for h in local_hosts:
        if h in url:
            return False
    return True


def _client_kwargs(backend: str, timeout: float) -> dict:
    """Build httpx client kwargs (proxy/headers/trust_env) for a backend."""
    headers = {"User-Agent": GFW_USER_AGENT}
    timeout_cfg = httpx.Timeout(timeout, connect=10.0)
    if backend in GFW_BACKENDS:
        url = BACKENDS.get(backend, {}).get("url", "")
        if _needs_proxy(url):
            return {"proxy": GFW_PROXY_URL, "headers": headers, "timeout": timeout_cfg, "limits": _LIMITS}
        return {"trust_env": False, "headers": headers, "timeout": timeout_cfg, "limits": _LIMITS}
    return {"trust_env": False, "timeout": timeout_cfg, "limits": _LIMITS}


class _SharedClient:
    """No-op context wrapper: yields a cached client without closing it on exit."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False


class _SharedAsyncClient:
    """No-op async context wrapper for a cached AsyncClient."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> Literal[False]:
        return False


def _build_client(backend: str, timeout: float) -> _SharedClient:
    with _CACHE_LOCK:
        client = _CLIENT_CACHE.get(backend)
        if client is None:
            client = httpx.Client(**_client_kwargs(backend, timeout))
            _CLIENT_CACHE[backend] = client
    return _SharedClient(client)


def _build_async_client(backend: str, timeout: float) -> _SharedAsyncClient:
    # AsyncClient must be created inside a running event loop; this is always
    # called from async call sites, so lazy creation here is loop-safe.
    with _CACHE_LOCK:
        client = _ASYNC_CLIENT_CACHE.get(backend)
        if client is None:
            client = httpx.AsyncClient(**_client_kwargs(backend, timeout))
            _ASYNC_CLIENT_CACHE[backend] = client
    return _SharedAsyncClient(client)


def invalidate_client_cache(backend: str | None = None) -> None:
    """Drop cached sync clients (one backend or all). Called on backend changes."""
    with _CACHE_LOCK:
        targets = [backend] if backend else list(_CLIENT_CACHE.keys())
        for name in targets:
            client = _CLIENT_CACHE.pop(name, None)
            if client is not None:
                try:
                    client.close()
                except Exception as exc:
                    _log.debug("closing cached client for %s failed: %s", name, exc)


async def aclose_all_clients() -> None:
    """Close all cached async clients (call on app shutdown)."""
    with _CACHE_LOCK:
        clients = list(_ASYNC_CLIENT_CACHE.values())
        _ASYNC_CLIENT_CACHE.clear()
    for client in clients:
        try:
            await client.aclose()
        except Exception as exc:
            _log.debug("aclose cached async client failed: %s", exc)


def reset_client_cache_for_tests() -> None:
    """Test hook: close and clear all cached clients (sync + async best-effort)."""
    with _CACHE_LOCK:
        for client in _CLIENT_CACHE.values():
            try:
                client.close()
            except Exception as exc:
                _log.debug("close cached client failed: %s", exc)
        _CLIENT_CACHE.clear()
        _ASYNC_CLIENT_CACHE.clear()
