from collections.abc import Callable

from .safety import redact_sensitive_query

Transport = Callable[[dict], dict]


class AnySearchAdapter:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        params = {
            "query": redact_sensitive_query(query),
            "max_results": max_results,
        }
        if domain:
            params["domain"] = domain
        return self._transport({"method": "search", "params": params})

    def batch_search(
        self,
        queries: list[str],
        *,
        domain: str | None = None,
        max_results: int = 5,
    ) -> dict:
        params = {
            "queries": [redact_sensitive_query(query) for query in queries],
            "max_results": max_results,
        }
        if domain:
            params["domain"] = domain
        return self._transport({"method": "batch_search", "params": params})

    def extract_url(self, url: str) -> dict:
        return self._transport({"method": "extract_url", "params": {"url": url}})
