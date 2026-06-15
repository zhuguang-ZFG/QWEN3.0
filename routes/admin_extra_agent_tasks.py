"""Admin API: agent task inspection and control."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()


@router.get("/api/agent-tasks", dependencies=[Depends(verify_admin)])
async def admin_agent_tasks(limit: int = 100):
    """List agent tasks with status summary."""
    store = _get_task_store()
    if not store:
        return {"tasks": [], "count": 0}
    raw = store.values() if hasattr(store, "values") else (store if isinstance(store, dict) else [])
    tasks = sorted(
        raw,
        key=lambda t: t.get("created_at", 0) if isinstance(t, dict) else 0,
        reverse=True,
    )[:limit]
    result = []
    for t in tasks:
        req = t.get("request", {}) if isinstance(t, dict) else {}
        result.append({
            "task_id": t.get("task_id", t.get("id", "")) if isinstance(t, dict) else "",
            "status": t.get("status", "unknown") if isinstance(t, dict) else "unknown",
            "created_at": t.get("created_at", 0) if isinstance(t, dict) else 0,
            "description": (req.get("goal", "") or req.get("description", ""))[:200],
            "worker_id": t.get("worker_id", t.get("claim", {}).get("worker_id", "")) if isinstance(t, dict) else "",
            "backend": t.get("backend", "") if isinstance(t, dict) else "",
        })
    return {"tasks": result, "count": len(result)}


@router.get("/api/agent-tasks/{task_id}", dependencies=[Depends(verify_admin)])
async def admin_agent_task_detail(task_id: str):
    store = _get_task_store()
    if not store:
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/api/agent-tasks/{task_id}/cancel", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_cancel_agent_task(task_id: str):
    store = _get_task_store()
    if not store or not hasattr(store, "get"):
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "cancel_requested"
    task["updated_at"] = time.time()
    return {"ok": True, "task_id": task_id, "status": "cancel_requested"}


@router.post("/api/agent-tasks/{task_id}/retry", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_retry_agent_task(task_id: str):
    store = _get_task_store()
    if not store or not hasattr(store, "get"):
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "pending"
    task["updated_at"] = time.time()
    return {"ok": True, "task_id": task_id, "status": "pending"}


def _get_task_store():
    try:
        from routes.agent_tasks import _store

        return _store
    except (ImportError, AttributeError):
        return None
