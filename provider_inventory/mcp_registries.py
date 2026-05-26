"""Read-only MCP registry inventory (PE-A-1)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

OFFICIAL_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
GLAMA_SERVERS_URL = "https://glama.ai/api/mcp/v1/servers"
SAFEMCP_URL = "https://safemcp.com/"

_TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("coding", ("git", "code", "github", "semgrep", "eslint", "compiler")),
    ("ops", ("grafana", "netdata", "cloudflare", "aws", "sentry", "datadog", "kubernetes")),
    ("search", ("search", "crawl", "tavily", "serp", "index")),
    ("browser", ("browser", "playwright", "puppeteer", "selenium")),
    ("data", ("postgres", "sql", "database", "neo4j", "qdrant", "sqlite", "redis")),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fetch_json(url: str, *, timeout: float = 25.0) -> Any:
    req = Request(
        url,
        headers={
            "User-Agent": "LiMa-MCP-Inventory/1.0 (+https://chat.donglicao.com)",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
        url = f"{OFFICIAL_REGISTRY_URL}?limit={page_size}"
        if cursor:
            url += f"&cursor={cursor}"
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
    name = str(raw.get("name") or raw.get("title") or slug).strip()
    if not name:
        return None
    desc = str(raw.get("description") or raw.get("summary") or "").strip()
    url = f"https://glama.ai/mcp/servers/{slug}" if slug else GLAMA_SERVERS_URL
    return {
        "key": _normalize_key(slug or name),
        "name": name,
        "title": name,
        "description": desc[:500],
        "source": "glama",
        "source_url": url,
        "repository_url": str(raw.get("repositoryUrl") or raw.get("repository_url") or ""),
        "tags": infer_tags(f"{name} {desc}"),
    }


def fetch_glama_servers() -> dict[str, Any]:
    try:
        payload = _fetch_json(GLAMA_SERVERS_URL)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"entries": [], "error": type(exc).__name__}
    servers = payload.get("servers") if isinstance(payload, dict) else payload
    if not isinstance(servers, list):
        return {"entries": [], "error": "unexpected_shape"}
    entries = []
    for item in servers:
        entry = _glama_entry(item)
        if entry:
            entries.append(entry)
    return {"entries": entries, "error": ""}


def fetch_safemcp_index() -> dict[str, Any]:
    """Best-effort SafeMCP scrape; returns empty entries on failure."""
    try:
        req = Request(
            SAFEMCP_URL,
            headers={"User-Agent": "LiMa-MCP-Inventory/1.0"},
        )
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"entries": [], "error": type(exc).__name__}
    links = re.findall(r'href="(https?://[^"]+mcp[^"]*)"', html, flags=re.I)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in links[:200]:
        key = _normalize_key(link)
        if not key or key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "key": key,
                "name": link.rsplit("/", 1)[-1][:80],
                "title": link,
                "description": "SafeMCP index link (HTML extract)",
                "source": "safemcp",
                "source_url": link,
                "repository_url": "",
                "tags": ["general"],
            }
        )
    return {"entries": entries, "error": ""}


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


def build_mcp_registry_snapshot(*, page_limit: int = 8) -> dict[str, Any]:
    official = fetch_official_registry(page_limit=page_limit)
    glama = fetch_glama_servers()
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
            "glama": {"url": GLAMA_SERVERS_URL, "error": glama.get("error", "")},
            "safemcp": {"url": SAFEMCP_URL, "error": safemcp.get("error", "")},
        },
        "servers": merged,
    }
