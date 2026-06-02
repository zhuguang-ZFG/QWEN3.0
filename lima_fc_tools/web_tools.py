"""Web browsing tools -- fetch and parse web pages."""

from __future__ import annotations

import json
import re
from typing import Any

from .http_client import _get
from .registry import tool


def _clean_text(text: str, max_len: int = 4000) -> str:
    """Collapse whitespace and truncate to *max_len* characters."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


@tool(
    "browse_webpage",
    "Fetch a web page and return its text content. "
    "Optionally extract elements matching a CSS-like selector (tag name or "
    "'tag.class'). Returns title, text, and links.",
    {
        "properties": {
            "url": {"description": "URL to fetch.", "type": "string"},
            "selector": {
                "default": "",
                "description": "Optional simple selector: tag name or 'tag.class'. "
                "If omitted, the full page text is returned.",
                "type": "string",
            },
            "max_length": {
                "default": 4000,
                "description": "Maximum characters of text to return.",
                "type": "integer",
            },
        },
        "required": ["url"],
        "type": "object",
    },
)
async def _browse_webpage(
    url: str,
    selector: str = "",
    max_length: int = 4000,
) -> dict[str, Any]:
    """Fetch *url* and return extracted content."""
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, verify=False
        ) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "LiMa-Bot/1.0 (web-tools)"},
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                try:
                    return {"url": url, "format": "json", "data": resp.json()}
                except Exception:
                    pass
            html = resp.text
    except Exception as exc:
        return {"error": str(exc), "url": url}

    # Simple HTML parsing without beautifulsoup4 dependency
    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = _clean_text(title_match.group(1), 200)

    # Extract links
    links: list[dict[str, str]] = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        text = _clean_text(re.sub(r"<[^>]+>", "", m.group(2)), 80)
        if text and href and not href.startswith(("#", "javascript:")):
            links.append({"text": text, "href": href})
        if len(links) >= 20:
            break

    # Extract body text
    body = html
    # Remove script/style blocks
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", body, flags=re.IGNORECASE | re.DOTALL)
    # Remove tags
    body = re.sub(r"<[^>]+>", " ", body)
    # Decode common entities
    body = body.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    body = body.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    body = _clean_text(body, max_length)

    if selector:
        # Simple selector: tag or tag.class
        tag = selector.split(".")[0].lower()
        cls = selector.split(".", 1)[1] if "." in selector else ""
        pattern = re.compile(
            rf"<{tag}\b[^>]*(?:class=[\"'][^\"']*{re.escape(cls)}[^\"']*[\"'])?[^>]*>(.*?)</{tag}>",
            re.IGNORECASE | re.DOTALL,
        )
        matches = pattern.findall(html)
        if matches:
            extracted = " ".join(
                _clean_text(re.sub(r"<[^>]+>", " ", m), max_length // max(len(matches), 1))
                for m in matches
            )
            return {
                "url": url,
                "title": title,
                "selector": selector,
                "text": extracted[:max_length],
                "links": links[:10],
            }
        return {"url": url, "title": title, "selector": selector, "text": "", "note": "No matches for selector", "links": links[:10]}

    return {"url": url, "title": title, "text": body, "links": links[:10]}


@tool(
    "fetch_url",
    "Fetch raw content from a URL. Returns JSON when possible, otherwise text.",
    {
        "properties": {
            "url": {"description": "URL to fetch.", "type": "string"},
        },
        "required": ["url"],
        "type": "object",
    },
)
async def _fetch_url(url: str) -> Any:
    """Simple URL fetch returning JSON or text."""
    try:
        result = await _get(url, timeout=10)
        return result
    except Exception as exc:
        return {"error": str(exc), "url": url}
