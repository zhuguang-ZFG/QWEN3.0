"""Web search discovery: find new AI API providers via search engines.

Uses SearXNG (local or remote) and Bing Search MCP to discover new free
AI API services through structured web searches.
"""

import logging
import os
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8081")

SEARCH_QUERIES = [
    # English
    "free LLM API endpoint 2025 2026",
    "free AI API no key required",
    "new free OpenAI compatible API",
    "free coding AI API gateway",
    # Chinese
    "免费大模型API接口 2025",
    "免费AI接口 无需注册",
    "新的免费大模型API",
    "免费编程AI接口",
]


@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""
    source_query: str = ""


_URL_PATTERN = re.compile(
    r"(https?://[^\s\)]+(?:api|gateway|v1|chat|completion)[^\s\)]*)",
    re.IGNORECASE,
)
_MODEL_PATTERN = re.compile(
    r"(?i)(gpt-?\d|claude|gemini|llama|qwen|deepseek|kimi|glm|mistral|grok|nemotron|minimax|step)",
)
_FREE_PATTERN = re.compile(r"(?i)(free|免费|no.?cost|no.?key|no.?auth)")


async def search_searxng(query: str, limit: int = 10) -> list[SearchResult]:
    """Search via SearXNG instance for new AI API providers."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            if resp.status_code != 200:
                logger.debug("SearXNG search failed: HTTP %d", resp.status_code)
                return []

            data = resp.json()
            results = []
            for item in data.get("results", [])[:limit]:
                snippet = item.get("content", "") or item.get("snippet", "")
                url = item.get("url", "")
                title = item.get("title", "")

                # Boost results that mention free + AI model
                if _FREE_PATTERN.search(snippet + title) and _MODEL_PATTERN.search(snippet + title):
                    results.append(
                        SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source_query=query,
                        )
                    )
            return results
    except Exception as exc:
        logger.warning("SearXNG search error: %s", type(exc).__name__)
        return []


async def search_bing(query: str) -> list[SearchResult]:
    """Search via Bing MCP (optional, requires MCP configured)."""
    # Bing MCP integration point - returns empty if not configured
    try:
        # The actual MCP call would go here
        # For now, return empty - Bing is a fallback to SearXNG
        return []
    except Exception:
        return []


def extract_api_urls(text: str) -> list[str]:
    """Extract potential API URLs from text content."""
    urls = _URL_PATTERN.findall(text)
    # Deduplicate and clean
    seen = set()
    clean = []
    for u in urls:
        u = u.rstrip(".,;:)]}'\"")
        if u not in seen and len(u) < 200:
            seen.add(u)
            clean.append(u)
    return clean


async def scan_web() -> list[dict]:
    """Run web search discovery across all configured queries.

    Returns list of discovered providers with metadata.
    """
    all_providers: list[dict] = []

    # Try SearXNG first (local)
    for query in SEARCH_QUERIES:
        logger.info("Searching: %s", query[:60])
        results = await search_searxng(query)
        for r in results:
            urls = extract_api_urls(r.snippet + " " + r.url)
            for url in urls:
                all_providers.append(
                    {
                        "source": "searxng",
                        "query": query,
                        "title": r.title,
                        "url": url,
                        "snippet": r.snippet[:300],
                        "is_free": bool(_FREE_PATTERN.search(r.snippet + r.title)),
                        "mentioned_models": _MODEL_PATTERN.findall(r.snippet + r.title),
                    }
                )

    # Fallback: Bing if SearXNG returned nothing
    if not all_providers:
        logger.info("SearXNG returned no results, trying Bing fallback")
        for query in SEARCH_QUERIES[:2]:
            results = await search_bing(query)
            for r in results:
                urls = extract_api_urls(r.snippet + " " + r.url)
                for url in urls:
                    all_providers.append(
                        {
                            "source": "bing",
                            "query": query,
                            "title": r.title,
                            "url": url,
                            "snippet": r.snippet[:300],
                            "is_free": bool(_FREE_PATTERN.search(r.snippet + r.title)),
                            "mentioned_models": _MODEL_PATTERN.findall(r.snippet + r.title),
                        }
                    )

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for p in all_providers:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            unique.append(p)

    logger.info("Web search: %d total, %d unique providers", len(all_providers), len(unique))
    return unique
