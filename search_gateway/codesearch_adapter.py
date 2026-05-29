"""Local codesearch CLI adapter for LiMa Code (LC-W-2, default off)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

_log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent


def codesearch_enabled() -> bool:
    return os.environ.get("CODESEARCH_MCP_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def allowlist_roots() -> list[Path]:
    raw = os.environ.get("CODESEARCH_INDEX_PATHS", str(_ROOT))
    roots: list[Path] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        path = Path(part).resolve()
        roots.append(path)
    return roots or [_ROOT]


def _resolve_search_root(path_hint: str | None) -> Path | None:
    roots = allowlist_roots()
    if not path_hint:
        return roots[0]
    candidate = Path(path_hint).resolve()
    for root in roots:
        try:
            candidate.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def _binary() -> str | None:
    return shutil.which("codesearch") or shutil.which("codesearch.exe")


def search_local_code(
    query: str,
    *,
    max_results: int = 5,
    path_hint: str | None = None,
    timeout: float = 120.0,
) -> dict:
    clean = (query or "").strip()
    if not clean:
        return {"ok": False, "error": "empty_query"}
    if not codesearch_enabled():
        return {"ok": False, "error": "codesearch_disabled"}

    exe = _binary()
    if not exe:
        return {"ok": False, "error": "codesearch_binary_missing"}

    root = _resolve_search_root(path_hint)
    if root is None:
        return {"ok": False, "error": "path_not_in_allowlist"}

    proc = subprocess.run(
        [
            exe,
            "search",
            clean,
            "-m",
            str(max(1, min(max_results, 20))),
            "--path",
            str(root),
            "--compact",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(root),
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "error:" in combined.lower():
        detail = combined.strip().splitlines()[-1][:200]
        return {"ok": False, "error": detail or "search_failed"}

    results = _parse_json_results(proc.stdout or "")
    if not results:
        results = _parse_compact_lines(proc.stdout or "")
    return {
        "ok": bool(results),
        "engine": "codesearch",
        "root": str(root),
        "query": clean,
        "results": results[:max_results],
        "error": None if results else "no_hits",
    }


def _parse_json_results(stdout: str) -> list[dict]:
    body = stdout.strip()
    if not body:
        return []
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    items = payload if isinstance(payload, list) else payload.get("results", [])
    parsed: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("file") or "")
        snippet = str(item.get("snippet") or item.get("content") or item.get("text") or "")[:800]
        score = item.get("score")
        parsed.append(
            {
                "path": path,
                "snippet": snippet,
                "score": score,
                "source": "codesearch",
            }
        )
    return parsed


def _parse_compact_lines(stdout: str) -> list[dict]:
    rows: list[dict] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text or text.startswith("20"):
            continue
        rows.append({"path": text[:240], "snippet": text[:800], "source": "codesearch"})
    return rows
