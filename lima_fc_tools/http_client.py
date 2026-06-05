"""Shared HTTP client for Telegram Function Calling tools."""

from typing import Any

import httpx

_http: httpx.AsyncClient | None = None


async def _get(url: str, params: dict[str, Any] | None = None, timeout: float = 10) -> dict[str, Any] | str:
    """GET a URL and return JSON when possible, otherwise text."""
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=timeout)
    response = await _http.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return response.text
