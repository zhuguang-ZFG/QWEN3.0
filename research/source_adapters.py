"""Unified adapter interface wrapping search_gateway adapters.

Normalizes results from different search backends (web, code, docs)
into a common SearchHit format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str
    score: float = 0.5
    source: str = "web"  # "web" | "code" | "docs"


async def search_web(query: str, max_results: int = 5) -> list[SearchHit]:
    """Search web sources via search_gateway adapters."""
    hits: list[SearchHit] = []

    try:
        from search_gateway.searxng_adapter import search as searxng_search
        results = await searxng_search(query, max_results=max_results)
        for r in results:
            hits.append(SearchHit(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", r.get("content", ""))[:300],
                score=r.get("score", 0.5),
                source="web",
            ))
        return hits
    except ImportError:
        _log.debug("searxng_adapter not available")
    except Exception as exc:
        _log.debug("searxng search failed: %s", exc)

    try:
        from search_gateway.brave_adapter import search as brave_search
        results = await brave_search(query, max_results=max_results)
        for r in results:
            hits.append(SearchHit(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("description", "")[:300],
                score=r.get("score", 0.5),
                source="web",
            ))
        return hits
    except ImportError:
        _log.debug("brave_adapter not available")
    except Exception as exc:
        _log.debug("brave search failed: %s", exc)

    return hits


async def search_code(query: str, max_results: int = 5) -> list[SearchHit]:
    """Search code via search_gateway code adapters."""
    hits: list[SearchHit] = []

    try:
        from search_gateway.codesearch_adapter import search as codesearch
        results = await codesearch(query, max_results=max_results)
        for r in results:
            hits.append(SearchHit(
                url=r.get("path", r.get("url", "")),
                title=r.get("path", "").split("/")[-1] if r.get("path") else "",
                snippet=r.get("snippet", r.get("content", ""))[:300],
                score=r.get("score", 0.5),
                source="code",
            ))
    except ImportError:
        _log.debug("codesearch_adapter not available")
    except Exception as exc:
        _log.debug("codesearch failed: %s", exc)

    return hits
