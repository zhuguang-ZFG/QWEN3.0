"""Resolve dev-search adapter: SearXNG (optional) with TinyFish fallback."""

from __future__ import annotations

from typing import Protocol


class DevSearchAdapter(Protocol):
    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def batch_search(
        self, queries: list[str], *, domain: str | None = None, max_results: int = 5
    ) -> dict: ...
    def extract_url(self, url: str) -> dict: ...


class _FallbackAdapter:
    """Try primary adapter; on failure use fallback (PE-D-1 graceful degrade)."""

    def __init__(self, primary: DevSearchAdapter, fallback: DevSearchAdapter) -> None:
        self._primary = primary
        self._fallback = fallback

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        result = self._primary.search(query, domain=domain, max_results=max_results)
        if result.get("ok") and (result.get("results") or []):
            return result
        fb = self._fallback.search(query, domain=domain, max_results=max_results)
        if fb.get("ok"):
            fb["fallback_from"] = "searxng"
        return fb

    def batch_search(
        self, queries: list[str], *, domain: str | None = None, max_results: int = 5
    ) -> dict:
        result = self._primary.batch_search(queries, domain=domain, max_results=max_results)
        if result.get("ok") and (result.get("results") or []):
            return result
        fb = self._fallback.batch_search(queries, domain=domain, max_results=max_results)
        if fb.get("ok"):
            fb["fallback_from"] = "searxng"
        return fb

    def extract_url(self, url: str) -> dict:
        result = self._primary.extract_url(url)
        if result.get("ok"):
            return result
        return self._fallback.extract_url(url)


def get_dev_search_adapter() -> DevSearchAdapter:
    from search_gateway.anysearch_adapter import AnySearchAdapter
    from search_gateway.searxng_adapter import SearXNGAdapter, searxng_enabled
    from search_gateway.tinyfish_transport import tinyfish_transport

    fallback = AnySearchAdapter(tinyfish_transport)
    if not searxng_enabled():
        return fallback
    primary = SearXNGAdapter.from_env()
    return _FallbackAdapter(primary, fallback)
