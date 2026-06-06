"""Admin Agent Task audit routes."""

from fastapi import APIRouter, Depends

from routes.admin_auth import verify_admin

router = APIRouter(prefix="/admin")


@router.get("/api/agent-audit", dependencies=[Depends(verify_admin)])
async def admin_agent_audit(limit: int = 20):
    from routes.agent_tasks import _store, _task_audit_item

    safe_limit = max(1, min(int(limit), 100))
    tasks = list(_store.values())
    tasks.sort(
        key=lambda t: t.get("updated_at", t.get("created_at", 0)),
        reverse=True,
    )
    items = [_task_audit_item(task) for task in tasks[:safe_limit]]
    return {"tasks": items, "count": len(items)}
