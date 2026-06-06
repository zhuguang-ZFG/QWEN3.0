"""Admin agent task management endpoints (extracted from admin_api)."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get("/api/agent-tasks", dependencies=[Depends(verify_admin)])
async def admin_agent_tasks(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List agent tasks with optional status filter and pagination."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        all_tasks = list(store.values())
        if status:
            all_tasks = [t for t in all_tasks if t.get("status") == status]
        all_tasks.sort(key=lambda t: t.get("created_at", 0), reverse=True)
        total = len(all_tasks)
        page = all_tasks[offset : offset + limit]

        items = []
        for t in page:
            request = t.get("request", {})
            items.append({
                "task_id": request.get("task_id", ""),
                "status": t.get("status", "unknown"),
                "created_at": t.get("created_at", 0),
                "updated_at": t.get("updated_at", 0),
                "worker_id": request.get("worker_id", ""),
                "backend": request.get("backend", ""),
                "description": request.get("description", ""),
                "has_result": "result" in t,
            })
        return {"tasks": items, "total": total, "offset": offset, "limit": limit}
    except ImportError:
        return {"tasks": [], "total": 0, "offset": 0, "limit": limit}


@router.get("/api/agent-tasks/{task_id}", dependencies=[Depends(verify_admin)])
async def admin_agent_task_detail(task_id: str):
    """Get detailed information about a specific agent task."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        events = store.get_events(task_id)
        return {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "created_at": task.get("created_at", 0),
            "updated_at": task.get("updated_at", 0),
            "request": task.get("request", {}),
            "result": task.get("result"),
            "events": events[-20:],
        }
    except ImportError:
        raise HTTPException(503, "Task store not available")


@router.post("/api/agent-tasks/{task_id}/cancel", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_agent_task_cancel(task_id: str):
    """Cancel an agent task by setting cancel_requested flag."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        current_status = task.get("status", "")
        if current_status in ("completed", "failed", "cancelled"):
            raise HTTPException(409, f"Cannot cancel task in {current_status} status")
        request = dict(task.get("request", {}))
        request["cancel_requested"] = True
        task["request"] = request
        task["updated_at"] = time.time()
        store.update(task_id)
        store.append_event(task_id, {"type": "cancel_requested", "by": "admin"})
        return {"task_id": task_id, "status": "cancel_requested"}
    except ImportError:
        raise HTTPException(503, "Task store not available")


@router.post("/api/agent-tasks/{task_id}/retry", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_agent_task_retry(task_id: str):
    """Retry a failed task by resetting its status to accepted."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        current_status = task.get("status", "")
        if current_status not in ("failed", "quarantined"):
            raise HTTPException(409, f"Cannot retry task in {current_status} status")
        task["status"] = "accepted"
        task["updated_at"] = time.time()
        if "result" in task:
            del task["result"]
        request = dict(task.get("request", {}))
        request["cancel_requested"] = False
        task["request"] = request
        store.update(task_id)
        store.append_event(task_id, {"type": "retry", "by": "admin"})
        return {"task_id": task_id, "status": "accepted"}
    except ImportError:
        raise HTTPException(503, "Task store not available")
