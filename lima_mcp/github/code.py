"""GitHub Code API — search code, read files, create branches."""

from __future__ import annotations

import logging
import urllib.parse

from lima_mcp.github._common import _api_request, _is_configured

_log = logging.getLogger(__name__)
def search_code(query: str, *, per_page: int = 10, language: str = "") -> dict:
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
        except Exception as exc:
            _log.warning("operation failed: %s", exc)
            decoded = content
        return {
            "ok": True,
            "path": result["data"].get("path", ""),
            "content": decoded[:12000],
            "size": result["data"].get("size", 0),
            "url": result["data"].get("html_url", ""),
        }
    return result


def create_branch(owner: str, repo: str, branch: str, from_ref: str = "main") -> dict:
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
