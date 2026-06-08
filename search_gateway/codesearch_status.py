"""Codesearch MCP status probe for local operators."""

from __future__ import annotations

import os

from search_gateway.codesearch_adapter import (
    _binary,
    allowlist_roots,
    codesearch_enabled,
    search_local_code,
)


def build_codesearch_status() -> str:
    enabled = codesearch_enabled()
    exe = _binary()
    roots = allowlist_roots()
    raw_paths = os.environ.get("CODESEARCH_INDEX_PATHS", "")
    lines = [
        "Codesearch MCP (LC-W-2)",
        f"CODESEARCH_MCP_ENABLED={'1' if enabled else '0'}",
        f"binary={'ok' if exe else 'missing'}",
        f"allowlist={len(roots)} root(s)",
    ]
    for root in roots[:3]:
        lines.append(f"· {root}")
    if len(roots) > 3:
        lines.append(f"… +{len(roots) - 3} more")
    if raw_paths.strip():
        lines.append(f"CODESEARCH_INDEX_PATHS={raw_paths[:120]}")
    if not enabled:
        lines.append("提示: 设 CODESEARCH_MCP_ENABLED=1 并安装 codesearch CLI")
    elif not exe:
        lines.append("提示: PATH 中无 codesearch / codesearch.exe")
    return "\n".join(lines)


def format_search_result(payload: dict) -> str:
    if not payload.get("ok"):
        err = payload.get("error") or "unknown"
        return f"Codesearch 失败: {err}"
    hits = payload.get("results") or []
    if not hits:
        return f"Codesearch: 无命中 query={payload.get('query', '')!r}"
    lines = [
        f"Codesearch 命中 {len(hits)}（root={payload.get('root', '?')}）",
    ]
    for item in hits[:5]:
        path = str(item.get("path") or "?")
        snippet = str(item.get("snippet") or "")[:120].replace("\n", " ")
        lines.append(f"· {path}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


def probe_search(query: str, *, max_results: int = 3) -> dict:
    return search_local_code(query, max_results=max_results)
