"""GitHub Issues API — create, list, get, comment, search."""

from __future__ import annotations

import urllib.parse

from lima_mcp.github._common import _api_request, _is_configured


def create_issue(owner: str, repo: str, title: str, body: str = "",
                 labels: list[str] | None = None, assignees: list[str] | None = None) -> dict:
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
