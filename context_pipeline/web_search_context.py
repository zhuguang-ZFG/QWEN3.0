"""
Web search context injection — detect and fulfill search/URL-fetch intent.

For chatbots without native tool-calling: detects when a user query
needs web search or URL fetching, executes it locally, and injects
results as a system message before the model sees the query.

Design:
- Intent detection: lightweight keyword matching (reuses search_gateway/policy.py)
- Search execution: tiered SearXNG → Tavily → Brave → TinyFish (from dev_adapter)
- URL fetching: regex-extract URLs from query, fetch via dev_tools.read_url()
- Result formatting: compact block with title/URL/snippet, ≤3000 chars
- Graceful degradation: any failure → silent skip, normal chat proceeds
"""

from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)

_MAX_RESULTS = 3
_MAX_CONTEXT_CHARS = 3000

# ── Expanded search intent keywords (conversational, not just dev) ───────────

_SEARCH_KEYWORDS = (
    # English
    "search", "latest", "current", "today", "news", "weather",
    "what is", "who is", "when did", "when was", "how to",
    "define", "definition", "meaning of",
    # Chinese
    "搜索", "查一下", "查下", "帮我查", "帮我搜", "搜一下",
    "最新", "最近", "今天", "天气", "新闻", "热点",
    "什么是", "是谁", "什么时候", "怎么",
    "定义", "意思", "含义",
    "联网", "上网", "在线",
    # URL patterns (always trigger fetch)
    "http://", "https://",
)


# Simple identity / greeting questions that should NOT trigger search
_IDENTITY_PATTERNS = (
    "你是谁", "你叫什么", "你的名字", "你是什么",
    "what is your name", "who are you",
)

# ── Video search intent keywords ──────────────────────────────────────────────

_VIDEO_KEYWORDS = (
    # Chinese
    "视频", "教程视频", "找视频", "视频教程", "demo视频", "演示视频",
    "录播", "回放", "直播录像", "直播回放", "找教程", "教学视频",
    # English
    "video", "tutorial video", "find video", "search video",
    "youtube", "bilibili", "b站", "B站",
)


def _detect_search_intent(query: str) -> bool:
    """Check if a user query likely needs web search.

    Returns True if the query contains search-trigger keywords or URLs,
    AND is not a simple identity/greeting question.
    """
    if not query or not isinstance(query, str):
        return False

    # Skip pure identity questions (they match "是谁" etc.)
    lowered = query.lower().strip()
    for pat in _IDENTITY_PATTERNS:
        if pat in lowered:
            return False

    return any(marker in lowered for marker in _SEARCH_KEYWORDS)


def _detect_video_intent(query: str) -> bool:
    """Check if a user query likely wants video results."""
    if not query or not isinstance(query, str):
        return False
    lowered = query.lower().strip()
    return any(marker in lowered for marker in _VIDEO_KEYWORDS)


# ── URL extraction ────────────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _extract_urls(text: str) -> list[str]:
    """Extract all HTTP(S) URLs from text."""
    return _URL_RE.findall(text)


# ── Public API ────────────────────────────────────────────────────────────────

def inject_web_search_context(
    query: str,
    messages: list[dict],
) -> tuple[list[dict], str]:
    """Detect search intent, execute search/URL-fetch, inject results.

    Returns:
        (new_messages, search_context_text)
        search_context_text is "" if no search was needed or it failed.
    """
    if not _detect_search_intent(query) and not _detect_video_intent(query):
        return list(messages), ""

    parts: list[str] = []

    # 1. URL fetching (if user pasted links)
    urls = _extract_urls(query)
    for url in urls[:2]:  # max 2 URLs
        try:
            content = _fetch_url(url)
            if content:
                parts.append(content)
        except Exception as exc:
            _log.debug("web_search: URL fetch failed for %s: %s", url, exc)

    # 2. Video search (if video intent detected — runs before text search)
    if _detect_video_intent(query):
        try:
            video_result = _execute_video_search(query)
            if video_result:
                parts.append(video_result)
        except Exception as exc:
            _log.debug("web_search: video search failed: %s", exc)

    # 3. Web search (standard text search)
    if _detect_search_intent(query):
        try:
            search_result = _execute_search(query)
            if search_result:
                parts.append(search_result)
        except Exception as exc:
            _log.debug("web_search: search failed: %s", exc)

    if not parts:
        return list(messages), ""

    enrichment = "\n\n".join(parts)
    search_msg = {"role": "system", "content": enrichment}

    result = list(messages)
    # Insert after the first existing system message, or at position 0
    insert_pos = 0
    for i, msg in enumerate(result):
        if isinstance(msg, dict) and msg.get("role") == "system":
            insert_pos = i + 1
        else:
            break
    result.insert(insert_pos, search_msg)
    return result, enrichment


def _execute_search(query: str) -> str:
    """Run a web search and return formatted results.

    Uses the tiered adapter (SearXNG → Tavily → Brave → TinyFish).
    Returns empty string on failure.
    """
    try:
        from search_gateway.dev_adapter import get_dev_search_adapter
        from search_gateway.dev_tools import _normalize_results

        adapter = get_dev_search_adapter()
        raw = adapter.search(query, max_results=_MAX_RESULTS)
        if not raw.get("ok"):
            _log.debug("web_search: adapter returned not ok: %s", raw.get("error", ""))
            return ""

        results = _normalize_results(raw, source="web")
        if not results:
            return ""

        return _format_search_results(query, results)
    except ImportError:
        _log.debug("web_search: search_gateway not available")
    except Exception as exc:
        _log.debug("web_search: search execution failed: %s", exc)
    return ""


def _format_search_results(query: str, results: list[dict]) -> str:
    """Format search results into a compact context block."""
    lines = [f"[网页搜索结果: \"{query[:80]}\"]"]
    total = len(lines[0])

    for i, r in enumerate(results[:_MAX_RESULTS], 1):
        title = str(r.get("title", ""))[:120]
        url = str(r.get("url", ""))[:200]
        snippet = str(r.get("snippet", ""))[:500]
        block = f"\n{i}. {title}\n   {url}\n   {snippet}"
        if total + len(block) > _MAX_CONTEXT_CHARS:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines)


# ── Video search ──────────────────────────────────────────────────────────────


def _execute_video_search(query: str) -> str:
    """Run a video-specific search via SearXNG and return formatted results.

    Bypasses the tiered adapter — directly uses SearXNG with categories=videos.
    Returns empty string on failure.
    """
    try:
        from search_gateway.searxng_adapter import SearXNGAdapter, searxng_enabled

        if not searxng_enabled():
            _log.debug("web_search: SearXNG not enabled, skipping video search")
            return ""

        adapter = SearXNGAdapter.from_env()
        raw = adapter.search(query, max_results=_MAX_RESULTS, categories="videos")
        if not raw.get("ok"):
            _log.debug(
                "web_search: video search adapter returned not ok: %s",
                raw.get("error", ""),
            )
            return ""

        results = raw.get("results") or []
        if not results:
            return ""

        return _format_video_results(query, results)
    except ImportError:
        _log.debug("web_search: searxng_adapter not available")
    except Exception as exc:
        _log.debug("web_search: video search execution failed: %s", exc)
    return ""


def _format_video_results(query: str, results: list[dict]) -> str:
    """Format video search results into a compact context block."""
    lines = [f"[视频搜索结果: \"{query[:80]}\"]"]
    total = len(lines[0])

    for i, r in enumerate(results[:_MAX_RESULTS], 1):
        title = str(r.get("title", ""))[:120]
        url = str(r.get("url", ""))[:200]
        snippet = str(r.get("snippet", ""))[:400]
        duration = str(r.get("duration", ""))
        uploader = str(r.get("uploader", ""))

        parts: list[str] = [f"\n{i}. {title}"]
        if duration:
            parts.append(f" ({duration})")
        parts.append(f"\n   {url}")
        if uploader:
            parts.append(f"\n   上传者: {uploader}")
        if snippet:
            parts.append(f"\n   {snippet}")

        block = "".join(parts)
        if total + len(block) > _MAX_CONTEXT_CHARS:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines)


def _fetch_url(url: str) -> str:
    """Fetch and return a URL's text content.

    Returns formatted block or empty string on failure.
    """
    try:
        from search_gateway.dev_adapter import get_dev_search_adapter
        from search_gateway.dev_tools import read_url

        adapter = get_dev_search_adapter()
        result = read_url(url, adapter=adapter, max_chars=2000)
        if not result.get("ok"):
            _log.debug("web_search: URL fetch not ok for %s: %s", url, result.get("error", ""))
            return ""

        title = result.get("title", url)[:120]
        text = result.get("text", "")[:_MAX_CONTEXT_CHARS]
        return f"[网页内容: {title}]\n{text}"
    except ImportError:
        _log.debug("web_search: search_gateway not available for URL fetch")
    except Exception as exc:
        _log.debug("web_search: URL fetch failed for %s: %s", url, exc)
    return ""
