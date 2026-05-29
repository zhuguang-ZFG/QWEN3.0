"""Shared GitHub API utilities."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
_TIMEOUT = 30


def _token() -> str:
    return os.getenv("GITHUB_TOKEN", "")


def _is_configured() -> bool:
    return bool(_token())


def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated GitHub REST API request."""
    token = _token()
    if not token:
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}

    url = f"{GITHUB_API_BASE}{path}"
    data = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "LiMa-MCP/1.0")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return {"ok": True, "status": resp.status, "data": json.loads(resp.read())}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        _log.warning("GitHub API %s %s: %s %s", method, path, exc.code, detail)
        return {"ok": False, "error": f"GitHub API {exc.code}: {detail[:200]}"}
    except Exception as exc:
        _log.warning("GitHub API %s %s: %s", method, path, exc)
        return {"ok": False, "error": str(exc)[:300]}
