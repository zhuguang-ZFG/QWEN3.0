"""Multi-source parallel search with dedup and ranking.

Fans out queries to multiple search adapters, deduplicates by URL/title,
ranks by relevance and source diversity, and returns structured results.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from research.source_adapters import SearchHit, search_web, search_code

_log = logging.getLogger(__name__)


@dataclass
class ResearchQuery:
    query: str
    max_results_per_source: int = 5
    sources: list[str] | None = None  # None = all sources
    include_code_search: bool = True


@dataclass
class ResearchResult:
    query: str
    hits: list[SearchHit]
    synthesized: str = ""
    duration_ms: float = 0.0
    sources_queried: list[str] = field(default_factory=list)


async def run_research(query: ResearchQuery) -> ResearchResult:
    """Execute multi-source research with parallel fan-out."""
    t0 = time.time()
    all_hits: list[SearchHit] = []

    tasks = [search_web(query.query, max_results=query.max_results_per_source)]
    source_names = ["web"]

    if query.include_code_search:
        tasks.append(search_code(query.query, max_results=query.max_results_per_source))
        source_names.append("code")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            _log.debug("search source %s failed: %s", source_names[i], result)
            continue
        all_hits.extend(result)

    deduped = _deduplicate(all_hits)
    ranked = _rank(deduped, query.query)

    duration = (time.time() - t0) * 1000

    return ResearchResult(
        query=query.query,
        hits=ranked,
        duration_ms=duration,
        sources_queried=source_names,
    )


def _deduplicate(hits: list[SearchHit]) -> list[SearchHit]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[SearchHit] = []

    for hit in hits:
        url_key = _normalize_url(hit.url)
        title_key = hit.title.lower().strip()[:50]

        if url_key in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue

        seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        result.append(hit)

    return result


def _rank(hits: list[SearchHit], query: str) -> list[SearchHit]:
    query_terms = set(query.lower().split())

    for hit in hits:
        text = f"{hit.title} {hit.snippet}".lower()
        term_hits = sum(1 for t in query_terms if t in text)
        source_bonus = 0.1 if hit.source in ("code", "docs") else 0.0
        hit.score = hit.score + term_hits * 0.05 + source_bonus

    return sorted(hits, key=lambda h: -h.score)[:20]


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()
    except Exception as exc:
        _log.warning("URL normalization failed for %s: %s", url, exc)
        return url.lower()
