"""Zhihu Global Search adapter — full-web search via Zhihu API.

Searches the entire web using Zhihu's global_search endpoint.
Requires ZHIHU_API_KEY environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

SEARCH_URL = "https://developer.zhihu.com/api/v1/content/global_search"


def search(
    query: str,
    *,
    domain: str | None = None,
    max_results: int = 10,
) -> dict:
    """Search the web via Zhihu Global Search API.

    Args:
        query: Search keywords
        domain: Optional domain filter (e.g., "github.com")
        max_results: Max results (1-20)

    Returns:
        {"ok": True, "results": [...], "total": int}
    """
    api_key = os.environ.get("ZHIHU_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "ZHIHU_API_KEY not configured"}

    count = min(max(1, max_results), 20)
    params = {"Query": query, "Count": str(count)}

    # Build URL with query params
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)

    # Add domain filter if specified
    if domain:
        filter_expr = f'host=="{domain}"'
        params["Filter"] = filter_expr
        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
        "User-Agent": "LiMa-Search/1.0",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        if data.get("Code") != 0:
            return {"ok": False, "error": data.get("Message", "Unknown error")}

        items = data.get("Data", {}).get("Items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("Title", ""),
                "url": item.get("Url", ""),
                "snippet": item.get("ContentText", ""),
                "type": item.get("ContentType", ""),
                "author": item.get("AuthorName", ""),
                "votes": item.get("VoteUpCount", 0),
                "comments": item.get("CommentCount", 0),
                "authority": item.get("AuthorityLevel", ""),
            })

        return {
            "ok": True,
            "results": results,
            "total": len(results),
            "has_more": data.get("Data", {}).get("HasMore", False),
        }

    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def search_zhihu(
    query: str,
    *,
    max_results: int = 10,
) -> dict:
    """Search Zhihu-specific content (questions, answers, articles)."""
    api_key = os.environ.get("ZHIHU_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "ZHIHU_API_KEY not configured"}

    count = min(max(1, max_results), 10)
    params = {"Query": query, "Count": str(count)}
    url = f"https://developer.zhihu.com/api/v1/content/zhihu_search?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
        "User-Agent": "LiMa-Search/1.0",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        if data.get("Code") != 0:
            return {"ok": False, "error": data.get("Message", "Unknown error")}

        items = data.get("Data", {}).get("Items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("Title", ""),
                "url": item.get("Url", ""),
                "snippet": item.get("ContentText", ""),
                "type": item.get("ContentType", ""),
                "author": item.get("AuthorName", ""),
                "votes": item.get("VoteUpCount", 0),
                "authority": item.get("AuthorityLevel", ""),
            })

        return {"ok": True, "results": results, "total": len(results)}

    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
