"""Read-only MCP registry inventory (PE-A-1)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from config import settings

logger = logging.getLogger(__name__)

OFFICIAL_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
GLAMA_SERVERS_URL = "https://glama.ai/api/mcp/v1/servers"
SAFEMCP_URLS = (
    "https://safemcp.com/",
    "https://www.safemcp.com/",
)

_TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("coding", ("git", "code", "github", "semgrep", "eslint", "compiler")),
    ("ops", ("grafana", "netdata", "cloudflare", "aws", "sentry", "datadog", "kubernetes")),
    ("search", ("search", "crawl", "tavily", "serp", "index")),
    ("browser", ("browser", "playwright", "puppeteer", "selenium")),
    ("data", ("postgres", "sql", "database", "neo4j", "qdrant", "sqlite", "redis")),
]

_FETCH_HEADERS = {
    "User-Agent": "LiMa-MCP-Inventory/1.0 (+https://chat.donglicao.com)",
    "Accept": "application/json, text/html;q=0.9",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fetch_text(url: str, *, timeout: float = 25.0, accept_json: bool = True) -> str:
    headers = dict(_FETCH_HEADERS)
    if not accept_json:
        headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
    proxy = settings.EMBEDDING.mcp_inventory_proxy or settings.EMBEDDING.gfw_proxy
    if proxy:
        try:
            import httpx

            with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            logger.warning("proxy fetch failed url=%s err=%s", url, type(exc).__name__)
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_json(url: str, *, timeout: float = 25.0) -> Any:
    return json.loads(_fetch_text(url, timeout=timeout, accept_json=True))


def _normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def infer_tags(text: str) -> list[str]:
    blob = (text or "").lower()
    tags = [label for label, keys in _TAG_RULES if any(k in blob for k in keys)]
    return tags or ["general"]


def _official_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    server = raw.get("server") if isinstance(raw, dict) else None
    if not isinstance(server, dict):
        return None
    name = str(server.get("name") or server.get("title") or "").strip()
    if not name:
        return None
    desc = str(server.get("description") or "").strip()
    repo = ""
    repository = server.get("repository")
    if isinstance(repository, dict):
        repo = str(repository.get("url") or "").strip()
    return {
        "key": _normalize_key(name),
        "name": name,
        "title": str(server.get("title") or name),
        "description": desc[:500],
        "source": "official_registry",
        "source_url": OFFICIAL_REGISTRY_URL,
        "repository_url": repo,
        "tags": infer_tags(f"{name} {desc}"),
    }


def fetch_official_registry(*, page_limit: int = 8, page_size: int = 100) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    cursor = ""
    pages = 0
    error = ""
    while pages < page_limit:
        params: dict[str, str | int] = {"limit": page_size}
        if cursor:
            params["cursor"] = cursor
        url = f"{OFFICIAL_REGISTRY_URL}?{urlencode(params)}"
        try:
            payload = _fetch_json(url)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            error = type(exc).__name__
            logger.warning("official registry fetch failed: %s", error)
            break
        servers = payload.get("servers") if isinstance(payload, dict) else None
        if not isinstance(servers, list) or not servers:
            break
        for item in servers:
            entry = _official_entry(item)
            if entry:
                entries.append(entry)
        meta = payload.get("metadata") if isinstance(payload, dict) else {}
        cursor = str(meta.get("nextCursor") or "").strip()
        pages += 1
        if not cursor:
            break
    return {"entries": entries, "pages_fetched": pages, "error": error}


def _glama_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    slug = str(raw.get("slug") or raw.get("id") or "").strip()
    namespace = str(raw.get("namespace") or "").strip()
    name = str(raw.get("name") or slug).strip()
    if not name and not slug:
        return None
    desc = str(raw.get("description") or raw.get("summary") or "").strip()
    full_slug = f"{namespace}/{slug}" if namespace and slug else slug or name
    page_url = str(raw.get("url") or "").strip()
    if not page_url and full_slug:
        page_url = f"https://glama.ai/mcp/servers/{quote(full_slug, safe='/')}"
    repo = ""
    repository = raw.get("repository")
    if isinstance(repository, dict):
        repo = str(repository.get("url") or "").strip()
    return {
        "key": _normalize_key(full_slug or name),
        "name": name or full_slug,
        "title": name or full_slug,
        "description": desc[:500],
        "source": "glama",
        "source_url": page_url or GLAMA_SERVERS_URL,
        "repository_url": repo,
        "tags": infer_tags(f"{name} {desc}"),
    }


def fetch_glama_servers(*, page_limit: int = 50) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    cursor = ""
    pages = 0
    error = ""
    while pages < page_limit:
        params: dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        url = GLAMA_SERVERS_URL
        if params:
            url = f"{GLAMA_SERVERS_URL}?{urlencode(params)}"
        try:
            payload = _fetch_json(url)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            error = type(exc).__name__
            logger.warning("glama fetch failed page=%s err=%s", pages, error)
            break
        servers = payload.get("servers") if isinstance(payload, dict) else None
        if not isinstance(servers, list):
            return {"entries": entries, "pages_fetched": pages, "error": error or "unexpected_shape"}
        if not servers:
            break
        for item in servers:
            entry = _glama_entry(item)
            if entry:
                entries.append(entry)
        page_info = payload.get("pageInfo") if isinstance(payload, dict) else {}
        if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
            pages += 1
            break
        cursor = str(page_info.get("endCursor") or "").strip()
        pages += 1
        if not cursor:
            break
    return {"entries": entries, "pages_fetched": pages, "error": error}


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


def fetch_safemcp_index() -> dict[str, Any]:
    """Best-effort SafeMCP scrape across known hostnames."""
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
            html = _fetch_text(base_url, timeout=20, accept_json=False)
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


def merge_registry_entries(*sources: dict[str, Any]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for block in sources:
        for entry in block.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or _normalize_key(str(entry.get("name", ""))))
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(entry)
                merged[key]["sources"] = [entry.get("source", "unknown")]
                continue
            existing = merged[key]
            src = entry.get("source", "unknown")
            if src not in existing["sources"]:
                existing["sources"].append(src)
            if not existing.get("description") and entry.get("description"):
                existing["description"] = entry["description"]
            if not existing.get("repository_url") and entry.get("repository_url"):
                existing["repository_url"] = entry["repository_url"]
    return sorted(merged.values(), key=lambda e: e.get("name", ""))


def build_mcp_registry_snapshot(
    *,
    official_page_limit: int = 8,
    glama_page_limit: int = 50,
) -> dict[str, Any]:
    official = fetch_official_registry(page_limit=official_page_limit)
    glama = fetch_glama_servers(page_limit=glama_page_limit)
    safemcp = fetch_safemcp_index()
    merged = merge_registry_entries(official, glama, safemcp)
    return {
        "generated_at": _utc_now(),
        "counts": {
            "merged": len(merged),
            "official": len(official.get("entries") or []),
            "glama": len(glama.get("entries") or []),
            "safemcp": len(safemcp.get("entries") or []),
        },
        "sources": {
            "official_registry": {
                "url": OFFICIAL_REGISTRY_URL,
                "pages_fetched": official.get("pages_fetched", 0),
                "error": official.get("error", ""),
            },
            "glama": {
                "url": GLAMA_SERVERS_URL,
                "pages_fetched": glama.get("pages_fetched", 0),
                "error": glama.get("error", ""),
            },
            "safemcp": {
                "urls": list(SAFEMCP_URLS),
                "error": safemcp.get("error", ""),
            },
        },
        "servers": merged,
    }
