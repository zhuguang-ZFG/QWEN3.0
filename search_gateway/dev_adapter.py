"""Dev-search adapter resolution: tiered SearXNG → Brave → TinyFish."""

from __future__ import annotations

from typing import Protocol


class DevSearchAdapter(Protocol):
    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def batch_search(
        self, queries: list[str], *, domain: str | None = None, max_results: int = 5
    ) -> dict: ...
    def extract_url(self, url: str) -> dict: ...


class _TieredAdapter:
    """Try tiers in order; use first adapter that returns non-empty results."""

    def __init__(self, tiers: list[tuple[str, DevSearchAdapter]]) -> None:
        self._tiers = tiers

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        last: dict = {"ok": False, "error": "no_search_tier"}
        for index, (_name, adapter) in enumerate(self._tiers):
            result = adapter.search(query, domain=domain, max_results=max_results)
            last = result
            if result.get("ok") and (result.get("results") or []):
                if index > 0:
                    result = {**result, "fallback_from": self._tiers[index - 1][0]}
                return result
        if last.get("ok"):
            return last
        return last

    def batch_search(
        self, queries: list[str], *, domain: str | None = None, max_results: int = 5
    ) -> dict:
        last: dict = {"ok": False, "error": "no_search_tier"}
        for index, (_name, adapter) in enumerate(self._tiers):
            result = adapter.batch_search(queries, domain=domain, max_results=max_results)
            last = result
            if result.get("ok") and (result.get("results") or []):
                if index > 0:
                    result = {**result, "fallback_from": self._tiers[index - 1][0]}
                return result
        if last.get("ok"):
            return last
        return last

    def extract_url(self, url: str) -> dict:
        for _name, adapter in self._tiers:
            result = adapter.extract_url(url)
            if result.get("ok"):
                return result
        return {"ok": False, "error": "extract_failed"}


def get_dev_search_adapter() -> DevSearchAdapter:
    from search_gateway.anysearch_adapter import AnySearchAdapter
    from search_gateway.brave_adapter import BraveSearchAdapter, brave_search_enabled
    from search_gateway.searxng_adapter import SearXNGAdapter, searxng_enabled
    from search_gateway.tinyfish_transport import tinyfish_transport

    tiers: list[tuple[str, DevSearchAdapter]] = []
    if searxng_enabled():
        tiers.append(("searxng", SearXNGAdapter.from_env()))
    if brave_search_enabled():
        tiers.append(("brave", BraveSearchAdapter.from_env()))
    tiers.append(("tinyfish", AnySearchAdapter(tinyfish_transport)))

    if len(tiers) == 1:
        return tiers[0][1]
    return _TieredAdapter(tiers)
