"""GitHub Pull Requests API — create, get, files, diff, review."""

from __future__ import annotations

from lima_mcp.github._common import _api_request, _is_configured, _token


def create_pull_request(
    owner: str, repo: str, title: str, head: str, base: str = "main",
    body: str = "",
) -> dict:
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


def get_pull_request(owner: str, repo: str, pr_number: int) -> dict:
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    result = _api_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if result.get("ok") and result.get("data"):
        pr = result["data"]
        return {
            "ok": True, "number": pr.get("number"), "title": pr.get("title", ""),
            "state": pr.get("state", ""), "body": (pr.get("body") or "")[:2000],
            "head": pr.get("head", {}).get("ref", ""),
            "base": pr.get("base", {}).get("ref", ""),
            "changed_files": pr.get("changed_files", 0),
            "url": pr.get("html_url", ""), "draft": pr.get("draft", False),
        }
    return result


def get_pull_request_files(owner: str, repo: str, pr_number: int, *, per_page: int = 20) -> dict:
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    params = f"per_page={min(per_page, 50)}"
    result = _api_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files?{params}")
    if result.get("ok") and isinstance(result.get("data"), list):
        files = result["data"]
        return {
            "ok": True, "files": [{
                "filename": f.get("filename", ""), "status": f.get("status", ""),
                "additions": f.get("additions", 0), "deletions": f.get("deletions", 0),
                "patch": (f.get("patch") or "")[:3000],
            } for f in files[:per_page]],
        }
    return result


def get_pull_request_diff(owner: str, repo: str, pr_number: int) -> dict:
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    result = _api_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if result.get("ok") and result.get("data"):
        diff_url = result["data"].get("diff_url", "")
        if diff_url:
            import urllib.request as _ur
            req = _ur.Request(diff_url, headers={"Authorization": f"Bearer {_token()}", "Accept": "application/vnd.github.v3.diff"})
            try:
                with _ur.urlopen(req, timeout=30) as resp:
                    diff_text = resp.read().decode("utf-8", errors="replace")
                    return {"ok": True, "diff": diff_text[:12000], "size": len(diff_text)}
            except Exception as exc:
                return {"ok": False, "error": f"diff fetch failed: {exc}"}
    return result


def create_review(owner: str, repo: str, pr_number: int, body: str, event: str = "COMMENT") -> dict:
    if not _is_configured():
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    if event not in {"APPROVE", "REQUEST_CHANGES", "COMMENT"}:
        event = "COMMENT"
    payload = {"body": body[:65536], "event": event}
    result = _api_request("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", payload)
    if result.get("ok") and result.get("data"):
        return {"ok": True, "id": result["data"].get("id"),
                "state": result["data"].get("state", ""),
                "url": result["data"].get("html_url", "")}
    return result
