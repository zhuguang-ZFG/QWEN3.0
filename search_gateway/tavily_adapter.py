"""Tavily search adapter for search_gateway."""

from __future__ import annotations

import os


def tavily_enabled() -> bool:
    return bool(os.environ.get("TAVILY_API_KEY", ""))


class TavilyAdapter:
    """Tavily web search adapter."""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    @classmethod
    def from_env(cls) -> TavilyAdapter:
        return cls(os.environ.get("TAVILY_API_KEY", ""))

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        import httpx

        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": max_results,
                    "include_answer": True,
                },
                timeout=15,
            )
            d = r.json()
            results = []
            for item in d.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300],
                    "source": "tavily",
                })
            answer = d.get("answer", "")
            return {
                "ok": True,
                "results": results,
                "answer": answer,
                "query": query,
                "provider": "tavily",
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "query": query}

    def batch_search(self, queries: list[str], *, domain: str | None = None, max_results: int = 5) -> dict:
        all_results = []
        for q in queries:
            r = self.search(q, domain=domain, max_results=max_results)
            all_results.extend(r.get("results", []))
        return {"ok": bool(all_results), "results": all_results, "provider": "tavily"}

    def extract_url(self, url: str) -> dict:
        import httpx

        try:
            r = httpx.post(
                "https://api.tavily.com/extract",
                json={"api_key": self._key, "urls": [url]},
                timeout=15,
            )
            d = r.json()
            results = d.get("results", [])
            if results:
                return {"ok": True, "content": results[0].get("raw_content", ""), "url": url}
            return {"ok": False, "error": "no_content", "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}
