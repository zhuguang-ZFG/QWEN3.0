"""Gitee OpenAPI v5 search helpers (radar P0 #3)."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from gitee_mirror import gitee_token_from_git_remotes

from .safety import sanitize_error_text

logger = logging.getLogger(__name__)

GITEE_API_BASE = "https://gitee.com/api/v5"
_DEFAULT_REPO = "zhuguang-cn/QWEN3.0"
_TIMEOUT = 20.0
_git_remote_token: str | None = None


def _access_token() -> str:
    global _git_remote_token
    env = (
        os.environ.get("GITEE_TOKEN", "").strip()
        or os.environ.get("GITEE_ACCESS_TOKEN", "").strip()
    )
    if env:
        return env
    if _git_remote_token is None:
        try:
            _git_remote_token = gitee_token_from_git_remotes()
        except OSError as exc:
            logger.debug("gitee git remote token fallback skipped err=%s", type(exc).__name__)
            _git_remote_token = ""
        except RuntimeError as exc:
            logger.warning("gitee git remote token fallback failed err=%s", type(exc).__name__)
            _git_remote_token = ""
    return _git_remote_token or ""


def credentials_configured() -> bool:
    return bool(_access_token())


def default_repo() -> str:
    return os.environ.get("GITEE_SEARCH_REPO", _DEFAULT_REPO).strip() or _DEFAULT_REPO


def _split_repo(repo: str) -> tuple[str, str]:
    parts = repo.strip().strip("/").split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repo must be owner/name")
    return parts[0], parts[1]


def _request_json(path: str, params: dict[str, str | int] | None = None) -> Any:
    token = _access_token()
    if not token:
        raise RuntimeError("GITEE_TOKEN not configured")

    query: dict[str, str | int] = {"access_token": token}
    if params:
        query.update(params)
    url = f"{GITEE_API_BASE}{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LiMa-Gitee-Search/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return __import__("json").loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"gitee_http_{exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"gitee_network: {exc.reason}") from exc


def _normalize_repo_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("full_name") or item.get("path") or "")
        out.append(
            {
                "title": str(item.get("name") or full_name or "repository")[:200],
                "url": str(item.get("html_url") or item.get("url") or "")[:300],
                "snippet": str(item.get("description") or "")[:500],
                "source": "gitee_repo",
                "repo": full_name,
            }
        )
    return out


def _normalize_issue_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or "issue")[:200],
                "url": str(item.get("html_url") or "")[:300],
                "snippet": str(item.get("body") or "")[:500],
                "source": "gitee_issue",
                "repo": str(item.get("repository", {}).get("full_name") or ""),
            }
        )
    return out


def search_repositories(query: str, *, max_results: int = 5) -> dict[str, Any]:
    clean = sanitize_error_text(query, max_chars=200)
    if not clean:
        return {"ok": False, "error": "empty_query"}
    if not credentials_configured():
        return {"ok": False, "error": "gitee_token_missing", "skipped": True}
    try:
        payload = _request_json(
            "/search/repositories",
            {"q": clean, "page": 1, "per_page": max(1, min(max_results, 20))},
        )
        return {"ok": True, "results": _normalize_repo_items(payload)}
    except RuntimeError as exc:
        logger.warning("gitee repo search failed err=%s", type(exc).__name__)
        return {"ok": False, "error": str(exc)[:240]}


def search_issues(
    query: str,
    *,
    repo: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    clean = sanitize_error_text(query, max_chars=200)
    if not clean:
        return {"ok": False, "error": "empty_query"}
    if not credentials_configured():
        return {"ok": False, "error": "gitee_token_missing", "skipped": True}
    params: dict[str, str | int] = {
        "q": clean,
        "page": 1,
        "per_page": max(1, min(max_results, 20)),
    }
    if repo:
        params["repo"] = repo.strip()
    try:
        payload = _request_json("/search/issues", params)
        return {"ok": True, "results": _normalize_issue_items(payload)}
    except RuntimeError as exc:
        logger.warning("gitee issue search failed err=%s", type(exc).__name__)
        return {"ok": False, "error": str(exc)[:240]}


def search_gitee(
    query: str,
    *,
    repo: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search Gitee code context: repo hits + scoped issue hits."""
    target_repo = repo or default_repo()
    repo_hits = search_repositories(query, max_results=max_results)
    issue_hits = search_issues(query, repo=target_repo, max_results=max_results)
    if not repo_hits.get("ok") and not issue_hits.get("ok"):
        err = issue_hits.get("error") or repo_hits.get("error") or "search_failed"
        skipped = bool(repo_hits.get("skipped") or issue_hits.get("skipped"))
        return {"ok": False, "error": err, "skipped": skipped}
    merged: list[dict[str, str]] = []
    if repo_hits.get("ok"):
        merged.extend(repo_hits.get("results") or [])
    if issue_hits.get("ok"):
        merged.extend(issue_hits.get("results") or [])
    return {
        "ok": True,
        "query": sanitize_error_text(query, max_chars=200),
        "repo": target_repo,
        "results": merged[: max(1, min(max_results, 20))],
    }


def fetch_repo_file(
    repo: str,
    path: str,
    *,
    ref: str = "master",
    max_chars: int = 8000,
) -> dict[str, Any]:
    if not credentials_configured():
        return {"ok": False, "error": "gitee_token_missing", "skipped": True}
    owner, name = _split_repo(repo)
    safe_path = path.strip().lstrip("/")
    if not safe_path:
        return {"ok": False, "error": "invalid_path"}
    encoded = "/".join(urllib.parse.quote(part) for part in safe_path.split("/"))
    try:
        payload = _request_json(
            f"/repos/{owner}/{name}/contents/{encoded}",
            {"ref": ref or "master"},
        )
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)[:240]}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "unexpected_payload"}
    import base64

    content = payload.get("content")
    if not isinstance(content, str):
        return {"ok": False, "error": "missing_content"}
    try:
        raw = base64.b64decode(content).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": f"decode_failed:{type(exc).__name__}"}
    return {
        "ok": True,
        "repo": repo,
        "path": safe_path,
        "ref": ref,
        "text": raw[:max_chars],
        "source": "gitee_file",
    }
