"""Public Experience Feeder v0.1 — search external knowledge sources.

Sources:
  - Stack Exchange / Stack Overflow API (free, no key required)
  - GitHub Issues Search (via existing GITHUB_TOKEN)
  - OSV.dev vulnerability API (free, no key required)

Results are normalized to a common format:
  {title, url, source, date, summary, confidence, tags}

Then optionally saved to typed memory via session_memory.

Privacy: only public queries are sent. No private code or tokens.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import time

_log = logging.getLogger(__name__)

_TIMEOUT = 15
_USER_AGENT = "LiMa-PublicFeeder/1.0"


def _get_json(url: str, *, headers: dict | None = None) -> dict:
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        _log.debug("feeder fetch failed: %s %s", url, type(exc).__name__)
        return {}


# ── Stack Exchange ──

def source_stackexchange_search(query: str, *, site: str = "stackoverflow", limit: int = 5) -> list[dict]:
    """Search Stack Exchange for questions/answers.

    Uses the public Stack Exchange API v2.2 (no key required for low volume).
    https://api.stackexchange.com/docs/search
    """
    params = urllib.parse.urlencode({
        "site": site,
        "pagesize": min(limit, 10),
        "order": "desc",
        "sort": "votes",
        "intitle": query[:150],
        "filter": "withbody",
    })
    url = f"https://api.stackexchange.com/2.3/search/advanced?{params}"
    data = _get_json(url)

    items = data.get("items", [])
    results: list[dict] = []
    for item in items[:limit]:
        results.append({
            "title": (item.get("title") or "")[:200],
            "url": item.get("link", ""),
            "source": "stackexchange",
            "date": time.strftime("%Y-%m-%d", time.gmtime(item.get("creation_date", 0))) if item.get("creation_date") else "",
            "summary": (item.get("body_markdown") or item.get("body", ""))[:500],
            "confidence": _stackexchange_confidence(item),
            "tags": item.get("tags", [])[:8],
        })
    return results


def _stackexchange_confidence(item: dict) -> float:
    score = item.get("score", 0)
    answered = 1 if item.get("is_answered") else 0
    answer_count = item.get("answer_count", 0)
    view_count = item.get("view_count", 0)
    # Simple heuristic: answered + high score + high views = higher confidence
    conf = 0.3 + answered * 0.2 + min(score / 100, 0.3) + min(answer_count / 20, 0.1) + min(view_count / 10000, 0.1)
    return round(min(conf, 0.95), 2)


# ── GitHub Issues Search ──

def source_github_issues_search(query: str, *, limit: int = 5) -> list[dict]:
    """Search GitHub issues for real-world bugs and experiences.

    Requires GITHUB_TOKEN in environment.
    """
    token = __import__("os").environ.get("GITHUB_TOKEN", "")
    if not token:
        return []

    q = urllib.parse.quote(f"{query} is:issue state:closed".replace(" ", "+"))
    url = f"https://api.github.com/search/issues?q={q}&sort=reactions&order=desc&per_page={min(limit, 10)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    data = _get_json(url, headers=headers)

    items = data.get("items", [])
    results: list[dict] = []
    for item in items[:limit]:
        results.append({
            "title": (item.get("title") or "")[:200],
            "url": item.get("html_url", ""),
            "source": "github_issues",
            "date": (item.get("closed_at") or item.get("created_at") or "")[:10],
            "summary": (item.get("body") or "")[:500],
            "confidence": _github_issue_confidence(item),
            "tags": [lb.get("name", "") for lb in item.get("labels", [])[:5]],
        })
    return results


def _github_issue_confidence(item: dict) -> float:
    reactions = item.get("reactions", {}).get("total_count", 0)
    comments = item.get("comments", 0)
    state = item.get("state", "")
    conf = 0.2
    if state == "closed":
        conf += 0.1
    conf += min(reactions / 50, 0.3) + min(comments / 20, 0.2)
    if item.get("pull_request"):
        conf += 0.1  # PRs often have real code changes
    return round(min(conf, 0.9), 2)


# ── OSV.dev ──

def source_osv_query(package: str, *, ecosystem: str = "PyPI") -> list[dict]:
    """Query OSV.dev for known vulnerabilities in a package.

    Free, no key required. https://osv.dev/docs/
    """
    body = json.dumps({
        "package": {"name": package, "ecosystem": ecosystem},
    }).encode()
    req = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        _log.debug("OSV query failed: %s %s", package, type(exc).__name__)
        return []

    vulns = data.get("vulns", [])
    results: list[dict] = []
    for v in vulns[:5]:
        vid = v.get("id", "")
        aliases = v.get("aliases", [])
        summary_text = v.get("summary", v.get("details", ""))[:300]
        results.append({
            "title": f"{vid}: {package}",
            "url": f"https://osv.dev/vulnerability/{vid}" if vid else "",
            "source": "osv",
            "date": v.get("modified", "")[:10],
            "summary": summary_text,
            "confidence": 0.9 if "critical" in str(v).lower() or "high" in str(v).lower() else 0.7,
            "tags": [package, ecosystem] + aliases[:3],
        })
    return results


# ── ESP-IDF Documentation Search ──

def source_espidf_search(query: str, *, limit: int = 5) -> list[dict]:
    """Search Espressif ESP-IDF documentation and examples."""
    results: list[dict] = []

    # DuckDuckGo site-restricted search for ESP-IDF docs
    try:
        encoded = urllib.parse.quote(f"{query} site:docs.espressif.com")
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
        data = _get_json(url)
        for item in data.get("RelatedTopics", [])[:limit]:
            if isinstance(item, dict):
                results.append({
                    "title": (item.get("Text") or item.get("FirstURL", ""))[:200],
                    "url": item.get("FirstURL", ""),
                    "source": "espidf_docs",
                    "date": "",
                    "summary": (item.get("Text") or "")[:400],
                    "confidence": 0.6,
                    "tags": ["esp32", "espidf", "documentation"],
                })
    except Exception:
        _log.debug("espidf search failed", exc_info=True)

    # Espressif GitHub examples
    try:
        token = __import__("os").environ.get("GITHUB_TOKEN", "")
        if token:
            q = urllib.parse.quote(f"{query} org:espressif topic:esp32")
            gh_url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page={min(limit, 5)}"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
            data = _get_json(gh_url, headers=headers)
            for item in data.get("items", [])[:limit]:
                results.append({
                    "title": f"ESP-IDF: {item.get('full_name', '')}"[:200],
                    "url": item.get("html_url", ""),
                    "source": "espidf_github",
                    "date": (item.get("updated_at") or "")[:10],
                    "summary": (item.get("description") or "")[:400],
                    "confidence": 0.55,
                    "tags": ["esp32", "espidf", "example"] + item.get("topics", [])[:3],
                })
    except Exception:
        _log.debug("espidf github search failed", exc_info=True)

    return results


# ── MCP Registry Search ──

def source_mcp_registry_search(query: str, *, limit: int = 5) -> list[dict]:
    """Search MCP registries (PulseMCP, Smithery) for available tools."""
    results: list[dict] = []

    # PulseMCP API
    try:
        encoded = urllib.parse.quote(query[:100])
        url = f"https://api.pulsemcp.com/v1/packages/search?q={encoded}&limit={min(limit, 5)}"
        data = _get_json(url)
        for item in data.get("packages", data.get("results", []))[:limit]:
            name = item.get("name", item.get("package_name", ""))
            results.append({
                "title": f"MCP: {name}"[:200],
                "url": item.get("homepage", item.get("github_url", "")),
                "source": "mcp_pulsemcp",
                "date": item.get("updated_at", "")[:10],
                "summary": item.get("description", "")[:400],
                "confidence": 0.4,
                "tags": ["mcp", "tool", name.lower()] if name else ["mcp"],
            })
    except Exception:
        _log.debug("pulsemcp search failed", exc_info=True)

    # Smithery Registry
    try:
        encoded = urllib.parse.quote(query[:100])
        url = f"https://registry.smithery.ai/api/v1/servers/search?q={encoded}&limit={min(limit, 5)}"
        data = _get_json(url)
        for item in data.get("servers", data.get("results", []))[:limit]:
            name = item.get("name", item.get("slug", ""))
            results.append({
                "title": f"MCP: {name}"[:200],
                "url": item.get("homepage", item.get("url", "")),
                "source": "mcp_smithery",
                "date": item.get("updated_at", "")[:10],
                "summary": item.get("description", "")[:400],
                "confidence": 0.4,
                "tags": ["mcp", "tool", name.lower()] if name else ["mcp"],
            })
    except Exception:
        _log.debug("smithery search failed", exc_info=True)

    return results


# ── Unified feeder ──

def feed_experience(
    query: str,
    *,
    sources: list[str] | None = None,
    limit: int = 3,
    save_to_memory: bool = False,
) -> dict:
    """Search multiple public experience sources and return unified results.

    Args:
        query: Search query
        sources: Which sources to search (default: all)
        limit: Max results per source
        save_to_memory: If True, save top results as typed memories

    Returns:
        {results: [...], saved_count: int}
    """
    sources = sources or ["stackexchange", "github_issues", "osv", "espidf", "mcp_registry"]
    all_results: list[dict] = []

    for src in sources:
        try:
            if src == "stackexchange":
                items = source_stackexchange_search(query, limit=limit)
            elif src == "github_issues":
                items = source_github_issues_search(query, limit=limit)
            elif src == "osv":
                items = source_osv_query(query)
            elif src == "espidf":
                items = source_espidf_search(query, limit=limit)
            elif src == "mcp_registry":
                items = source_mcp_registry_search(query, limit=limit)
            else:
                continue
            all_results.extend(items)
        except Exception as exc:
            _log.debug("source %s failed: %s", src, exc)

    # Sort by confidence
    all_results.sort(key=lambda r: r.get("confidence", 0), reverse=True)

    saved = 0
    if save_to_memory and all_results:
        try:
            from session_memory.store_promote import save_typed_memory

            for item in all_results[:5]:
                if item.get("confidence", 0) < 0.4:
                    continue
                memory_type = "security_lesson" if item["source"] == "osv" else "reference_pattern"
                save_typed_memory(
                    memory_type=memory_type,
                    summary=item["title"][:200],
                    detail=f"{item['summary'][:120]} | {item['url']}",
                    session_id="_global",
                )
                saved += 1
        except Exception as exc:
            _log.debug("save to memory failed: %s", exc)

    return {"results": all_results[:10], "saved_count": saved, "query": query}
