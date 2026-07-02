"""SafeMCP HTML 抓取 — 从 mcp_registries.py 拆出以控制行数。

依赖 _fetch_text（仍在 mcp_registries），通过函数签名注入避免循环导入；
_fetch_text 由调用方在 build_mcp_registry_snapshot 上下文传入，或由
mcp_registries re-export 时延迟绑定。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.error import HTTPError, URLError

SAFEMCP_URLS = (
    "https://safemcp.com/",
    "https://www.safemcp.com/",
)


def _normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _safemcp_entry(link: str) -> dict[str, Any]:
    return {
        "key": _normalize_key(link),
        "name": link.rsplit("/", 1)[-1][:80] or link,
        "title": link,
        "description": "SafeMCP index link (HTML extract)",
        "source": "safemcp",
        "source_url": link,
        "repository_url": "",
        "tags": ["general"],
    }


def fetch_safemcp_index(fetch_text) -> dict[str, Any]:
    """Best-effort SafeMCP scrape across known hostnames.

    Args:
        fetch_text: callable(url, *, timeout, accept_json) -> str，由调用方注入
            （mcp_registries._fetch_text），保持 monkeypatch 兼容。
    """
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    patterns = (
        r'href="(https?://[^"]+/mcp[^"]*)"',
        r'href="(https?://[^"]*safemcp[^"]*)"',
        r'href="(https?://glama\.ai/mcp/servers/[^"]+)"',
    )
    for base_url in SAFEMCP_URLS:
        try:
            html = fetch_text(base_url, timeout=20, accept_json=False)
        except (HTTPError, URLError, TimeoutError) as exc:
            errors.append(f"{base_url}:{type(exc).__name__}")
            continue
        if "lander" in html[:500].lower() and len(html) < 2000:
            errors.append(f"{base_url}:lander_redirect")
            continue
        for pattern in patterns:
            for link in re.findall(pattern, html, flags=re.I):
                if link in seen:
                    continue
                seen.add(link)
                entries.append(_safemcp_entry(link))
    return {
        "entries": entries[:300],
        "error": ";".join(errors) if errors and not entries else "",
    }