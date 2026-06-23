"""HTTP client factory helpers."""

from __future__ import annotations

import httpx

from backends_constants import GFW_BACKENDS
from backends_registry import BACKENDS
from config import settings

GFW_PROXY_URL = settings.EMBEDDING.gfw_proxy or "http://127.0.0.1:7897"
GFW_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _needs_proxy(url: str) -> bool:
    """Check if a URL should use the outbound proxy (skip local URLs)."""
    local_hosts = ("127.0.0.1", "localhost", "0.0.0.0")
    for h in local_hosts:
        if h in url:
            return False
    return True


def _build_client(backend: str, timeout: float) -> httpx.Client:
    proxy_url = GFW_PROXY_URL
    headers = {"User-Agent": GFW_USER_AGENT}
    timeout_cfg = httpx.Timeout(timeout, connect=10.0)
    if backend in GFW_BACKENDS:
        url = BACKENDS.get(backend, {}).get("url", "")
        if _needs_proxy(url):
            return httpx.Client(proxy=proxy_url, headers=headers, timeout=timeout_cfg)
        return httpx.Client(trust_env=False, headers=headers, timeout=timeout_cfg)
    return httpx.Client(trust_env=False, timeout=timeout_cfg)


def _build_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    proxy_url = GFW_PROXY_URL
    headers = {"User-Agent": GFW_USER_AGENT}
    timeout_cfg = httpx.Timeout(timeout, connect=10.0)
    if backend in GFW_BACKENDS:
        url = BACKENDS.get(backend, {}).get("url", "")
        if _needs_proxy(url):
            return httpx.AsyncClient(proxy=proxy_url, headers=headers, timeout=timeout_cfg)
        return httpx.AsyncClient(trust_env=False, headers=headers, timeout=timeout_cfg)
    return httpx.AsyncClient(trust_env=False, timeout=timeout_cfg)
