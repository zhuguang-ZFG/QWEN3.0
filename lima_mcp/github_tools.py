"""GitHub REST API tools — native issue/PR management for LiMa Code.

Uses GITHUB_TOKEN from environment (same token as backends_registry.py).
All operations are gated behind lima_mcp access control (Bearer token).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
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


def create_issue(owner: str, repo: str, title: str, body: str = "",
                 labels: list[str] | None = None, assignees: list[str] | None = None) -> dict:
    """Create a GitHub issue."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not title:
        return {"ok": False, "error": "owner, repo, and title are required"}

    payload: dict = {"title": title[:256], "body": body[:65536]}
    if labels:
        payload["labels"] = labels[:10]
    if assignees:
        payload["assignees"] = assignees[:10]

    result = _api_request("POST", f"/repos/{owner}/{repo}/issues", payload)
    if result.get("ok") and result.get("data"):
        issue = result["data"]
        return {
            "ok": True,
            "issue_url": issue.get("html_url", ""),
            "issue_number": issue.get("number"),
            "title": issue.get("title", ""),
            "state": issue.get("state", ""),
        }
    return result


def list_issues(owner: str, repo: str, *, state: str = "open",
                labels: str = "", per_page: int = 10) -> dict:
    """List issues in a GitHub repository."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo:
        return {"ok": False, "error": "owner and repo are required"}

    params = f"state={state}&per_page={min(per_page, 30)}&sort=updated"
    if labels:
        params += f"&labels={labels}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/issues?{params}")
    if result.get("ok") and isinstance(result.get("data"), list):
        issues = result["data"]
        return {
            "ok": True,
            "issues": [{
                "number": i.get("number"),
                "title": i.get("title", ""),
                "state": i.get("state", ""),
                "url": i.get("html_url", ""),
                "labels": [lb.get("name", "") for lb in (i.get("labels") or [])],
            } for i in issues[:per_page]],
            "count": len(issues[:per_page]),
        }
    return result


def get_issue(owner: str, repo: str, issue_number: int) -> dict:
    """Get a single GitHub issue by number."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not issue_number:
        return {"ok": False, "error": "owner, repo, and issue_number are required"}

    result = _api_request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
    if result.get("ok") and result.get("data"):
        issue = result["data"]
        return {
            "ok": True,
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "body": (issue.get("body") or "")[:4000],
            "state": issue.get("state", ""),
            "url": issue.get("html_url", ""),
            "labels": [lb.get("name", "") for lb in (issue.get("labels") or [])],
            "comments": issue.get("comments", 0),
        }
    return result


def add_issue_comment(owner: str, repo: str, issue_number: int, body: str) -> dict:
    """Add a comment to a GitHub issue."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not issue_number or not body:
        return {"ok": False, "error": "owner, repo, issue_number, and body are required"}

    result = _api_request(
        "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        {"body": body[:65536]},
    )
    if result.get("ok") and result.get("data"):
        comment = result["data"]
        return {
            "ok": True,
            "comment_url": comment.get("html_url", ""),
            "id": comment.get("id"),
        }
    return result


def search_issues(query: str, *, per_page: int = 10) -> dict:
    """Search GitHub issues across repositories."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not query:
        return {"ok": False, "error": "query is required"}

    params = f"q={urllib.parse.quote(query)}&per_page={min(per_page, 20)}"
    result = _api_request("GET", f"/search/issues?{params}")
    if result.get("ok") and result.get("data"):
        items = result["data"].get("items", [])
        return {
            "ok": True,
            "total_count": result["data"].get("total_count", 0),
            "issues": [{
                "number": i.get("number"),
                "title": i.get("title", ""),
                "state": i.get("state", ""),
                "url": i.get("html_url", ""),
                "repo": i.get("repository_url", "").split("/repos/")[-1] if i.get("repository_url") else "",
            } for i in items[:per_page]],
        }
    return result


def search_code(query: str, *, per_page: int = 10, language: str = "") -> dict:
    """Search GitHub code across public repositories."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not query:
        return {"ok": False, "error": "query is required"}

    q = urllib.parse.quote(query)
    if language:
        q += f"+language:{urllib.parse.quote(language)}"
    params = f"q={q}&per_page={min(per_page, 20)}"
    result = _api_request("GET", f"/search/code?{params}")
    if result.get("ok") and result.get("data"):
        items = result["data"].get("items", [])
        return {
            "ok": True,
            "total_count": result["data"].get("total_count", 0),
            "results": [{
                "name": i.get("name", ""),
                "path": i.get("path", ""),
                "repo": i.get("repository", {}).get("full_name", ""),
                "url": i.get("html_url", ""),
            } for i in items[:per_page]],
        }
    return result


def get_file_contents(owner: str, repo: str, path: str, ref: str = "main") -> dict:
    """Read file contents from a GitHub repository."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not path:
        return {"ok": False, "error": "owner, repo, and path are required"}

    safe_ref = urllib.parse.quote(ref.strip() or "main", safe="/.")
    safe_path = urllib.parse.quote(path.strip("/"), safe="/")
    result = _api_request(
        "GET", f"/repos/{owner}/{repo}/contents/{safe_path}?ref={safe_ref}",
    )
    if result.get("ok") and result.get("data"):
        import base64
        content = result["data"].get("content", "")
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            decoded = content
        return {
            "ok": True,
            "path": result["data"].get("path", ""),
            "content": decoded[:12000],
            "size": result["data"].get("size", 0),
            "url": result["data"].get("html_url", ""),
        }
    return result


def create_pull_request(
    owner: str, repo: str, title: str, head: str, base: str = "main",
    body: str = "",
) -> dict:
    """Create a GitHub pull request."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not title or not head:
        return {"ok": False, "error": "owner, repo, title, and head are required"}

    payload = {
        "title": title[:256],
        "head": head,
        "base": base,
        "body": body[:65536],
    }
    result = _api_request("POST", f"/repos/{owner}/{repo}/pulls", payload)
    if result.get("ok") and result.get("data"):
        pr = result["data"]
        return {
            "ok": True,
            "pr_url": pr.get("html_url", ""),
            "pr_number": pr.get("number"),
            "title": pr.get("title", ""),
            "state": pr.get("state", ""),
        }
    return result


def create_branch(owner: str, repo: str, branch: str, from_ref: str = "main") -> dict:
    """Create a new branch from an existing ref."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo or not branch:
        return {"ok": False, "error": "owner, repo, and branch are required"}

    ref_result = _api_request(
        "GET", f"/repos/{owner}/{repo}/git/ref/heads/{urllib.parse.quote(from_ref, safe='')}",
    )
    if not ref_result.get("ok"):
        return {"ok": False, "error": f"source ref not found: {from_ref}"}
    sha = ref_result["data"]["object"]["sha"]

    payload = {"ref": f"refs/heads/{branch}", "sha": sha}
    result = _api_request("POST", f"/repos/{owner}/{repo}/git/refs", payload)
    if result.get("ok") and result.get("data"):
        return {
            "ok": True,
            "ref": result["data"].get("ref", ""),
            "sha": result["data"]["object"].get("sha", ""),
        }
    return result
