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


# ── CI Evidence (read-only) ──


def list_workflow_runs(owner: str, repo: str, *, branch: str = "", per_page: int = 10, status: str = "") -> dict:
    """List recent workflow runs for a repository."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if not owner or not repo:
        return {"ok": False, "error": "owner and repo are required"}
    params = f"per_page={min(per_page, 20)}"
    if branch:
        params += f"&branch={urllib.parse.quote(branch)}"
    if status:
        params += f"&status={urllib.parse.quote(status)}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/actions/runs?{params}")
    if result.get("ok") and result.get("data"):
        runs = result["data"].get("workflow_runs", [])
        return {
            "ok": True, "total_count": result["data"].get("total_count", 0),
            "runs": [{
                "id": r.get("id"), "name": r.get("name"), "status": r.get("status"),
                "conclusion": r.get("conclusion"), "branch": r.get("head_branch"),
                "sha": (r.get("head_sha") or "")[:7], "url": r.get("html_url"),
                "created_at": r.get("created_at", ""),
            } for r in runs[:per_page]],
        }
    return result


def get_workflow_run(owner: str, repo: str, run_id: int) -> dict:
    """Get details of a specific workflow run."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    result = _api_request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")
    if result.get("ok") and result.get("data"):
        r = result["data"]
        return {
            "ok": True,
            "id": r.get("id"), "name": r.get("name"), "status": r.get("status"),
            "conclusion": r.get("conclusion"), "branch": r.get("head_branch"),
            "sha": (r.get("head_sha") or "")[:7], "url": r.get("html_url"),
            "created_at": r.get("created_at", ""), "event": r.get("event", ""),
        }
    return result


def list_workflow_jobs(owner: str, repo: str, run_id: int, *, per_page: int = 20) -> dict:
    """List jobs for a workflow run."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    params = f"per_page={min(per_page, 30)}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?{params}")
    if result.get("ok") and result.get("data"):
        jobs = result["data"].get("jobs", [])
        return {
            "ok": True, "total_count": result["data"].get("total_count", 0),
            "jobs": [{
                "id": j.get("id"), "name": j.get("name"), "status": j.get("status"),
                "conclusion": j.get("conclusion"), "started_at": j.get("started_at", ""),
                "completed_at": j.get("completed_at", ""), "url": j.get("html_url"),
                "steps": [{"name": s.get("name"), "status": s.get("status"), "conclusion": s.get("conclusion")}
                          for s in j.get("steps", [])[-6:]],
            } for j in jobs[:per_page]],
        }
    return result


def list_workflow_artifacts(owner: str, repo: str, *, per_page: int = 10) -> dict:
    """List artifacts for a repository."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    params = f"per_page={min(per_page, 20)}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/actions/artifacts?{params}")
    if result.get("ok") and result.get("data"):
        arts = result["data"].get("artifacts", [])
        size = sum(a.get("size_in_bytes", 0) for a in arts)
        return {
            "ok": True, "total_count": result["data"].get("total_count", 0),
            "total_size_kb": round(size / 1024, 1),
            "artifacts": [{
                "id": a.get("id"), "name": a.get("name"),
                "size_kb": round(a.get("size_in_bytes", 0) / 1024, 1),
                "workflow_run_id": a.get("workflow_run", {}).get("id"),
                "expired": a.get("expired", False),
            } for a in arts[:per_page]],
        }
    return result


def get_combined_status(owner: str, repo: str, ref: str) -> dict:
    """Get combined commit status for a ref (branch/SHA)."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    result = _api_request("GET", f"/repos/{owner}/{repo}/commits/{urllib.parse.quote(ref)}/status")
    if result.get("ok") and result.get("data"):
        return {
            "ok": True,
            "state": result["data"].get("state", "unknown"),
            "total_count": result["data"].get("total_count", 0),
            "statuses": [{
                "context": s.get("context", ""), "state": s.get("state", ""),
                "description": (s.get("description") or "")[:100],
            } for s in result["data"].get("statuses", [])[:10]],
        }
    return result


def list_check_runs(owner: str, repo: str, ref: str, *, per_page: int = 10) -> dict:
    """List check runs for a ref (branch/SHA)."""
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    params = f"per_page={min(per_page, 20)}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/commits/{urllib.parse.quote(ref)}/check-runs?{params}")
    if result.get("ok") and result.get("data"):
        checks = result["data"].get("check_runs", [])
        return {
            "ok": True, "total_count": result["data"].get("total_count", 0),
            "checks": [{
                "id": c.get("id"), "name": c.get("name"), "status": c.get("status"),
                "conclusion": c.get("conclusion"), "url": c.get("html_url"),
            } for c in checks[:per_page]],
        }
    return result
