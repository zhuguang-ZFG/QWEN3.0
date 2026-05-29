"""GitHub Workflows API — runs, jobs, artifacts, status, check runs."""

from __future__ import annotations

import urllib.parse

from lima_mcp.github._common import _api_request, _is_configured


def list_workflow_runs(owner: str, repo: str, *, branch: str = "", per_page: int = 10, status: str = "") -> dict:
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
