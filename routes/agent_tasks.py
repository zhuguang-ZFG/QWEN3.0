"""Agent task HTTP routes — SQLite-backed persistence."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from agent_contracts.task_contract import AgentTaskResult
from agent_evolution.candidates import get_candidate_store
from routes.agent_task_evolution import router as evolution_router
from routes.agent_task_schemas import (
    ClaimBody,
    ReviewBody,
    TaskCreateBody,
    TaskResultBody,
    WorkerSmokeTaskBody,
)
from routes.agent_task_service import (
    apply_task_review,
    create_task_from_body,
    latest_task_id,
    post_result_hooks,
    require_admin,
    task_audit_item,
    task_counts,
    task_envelope,
)
from routes.agent_task_store import TaskStore, _DB_PATH, get_task_store, reset_task_store_for_tests

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent")
router.include_router(evolution_router)

# Back-compat for tests and ops_metrics
_TaskStore = TaskStore
_store = get_task_store()
_task_audit_item = task_audit_item


def _reset_for_tests() -> None:
    reset_task_store_for_tests()
    get_candidate_store().clear_for_tests()


async def _require_admin(authorization: str = Header(default="")) -> None:
    await require_admin(authorization)


@router.post("/tasks", dependencies=[Depends(_require_admin)])
async def create_task(body: TaskCreateBody):
    return create_task_from_body(body)


@router.get("/tasks", dependencies=[Depends(_require_admin)])
async def list_tasks(
    status: str = Query(default="accepted"),
    limit: int = Query(default=1, ge=1, le=100),
):
    matches = [t for t in _store.values() if not status or t.get("status") == status]
    matches.sort(key=lambda t: t.get("created_at", 0))
    return {
        "tasks": [t["request"] for t in matches[:limit]],
        "count": len(matches[:limit]),
    }


@router.get("/audit", dependencies=[Depends(_require_admin)])
async def agent_audit(limit: int = Query(default=20, ge=1, le=100)):
    tasks = list(_store.values())
    tasks.sort(
        key=lambda t: t.get("updated_at", t.get("created_at", 0)),
        reverse=True,
    )
    items = [task_audit_item(task) for task in tasks[:limit]]
    return {"tasks": items, "count": len(items)}


@router.get("/worker/preflight", dependencies=[Depends(_require_admin)])
async def worker_preflight():
    return {
        "ready": True,
        "contract_version": "agent-task-v1+prompt-contract-v0.1",
        "server_time": time.time(),
        "counts": task_counts(),
        "latest_task_id": latest_task_id(),
        "features": {
            "create": True,
            "list": True,
            "claim": True,
            "cancel": True,
            "control": True,
            "result": True,
            "review": True,
            "quarantine": True,
            "audit": True,
            "smoke_task": True,
        },
    }


@router.post("/worker/smoke-task", dependencies=[Depends(_require_admin)])
async def create_worker_smoke_task(body: WorkerSmokeTaskBody):
    if body.kind == "patch_readme":
        task = TaskCreateBody(
            repo=body.repo,
            branch=body.branch,
            goal=(
                "LiMa Code real-machine patch smoke: replace README with a "
                "harmless marker and run node --version."
            ),
            constraints=[
                "Smoke task only.",
                "Do not commit.",
                "Do not deploy.",
                "Return needs_review after patch and test evidence.",
            ],
            allowed_tools=["write", "git_diff", "test"],
            max_runtime_sec=120,
            mode="patch",
            patch_files=[{"file_path": "README.md", "content": "# LiMa Code Smoke\n"}],
            test_commands=["node --version"],
        )
    else:
        task = TaskCreateBody(
            repo=body.repo,
            branch=body.branch,
            goal=(
                "LiMa Code real-machine read-only smoke: review current git "
                "diff and report evidence."
            ),
            constraints=[
                "Read-only smoke task.",
                "Do not edit files.",
                "Do not commit.",
                "Return needs_review with changed_files empty unless local diff already exists.",
            ],
            allowed_tools=["git_diff"],
            max_runtime_sec=120,
            mode="review",
        )
    return create_task_from_body(task)


@router.get("/tasks/{task_id}", dependencies=[Depends(_require_admin)])
async def get_task(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    return task_envelope(_store.get(task_id))


@router.post("/tasks/{task_id}/claim", dependencies=[Depends(_require_admin)])
async def claim_task(task_id: str, body: ClaimBody):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    try:
        task = _store.claim(task_id, body.worker_id, body.lease_sec)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return task_envelope(task)


@router.post("/tasks/{task_id}/cancel", dependencies=[Depends(_require_admin)])
async def cancel_task(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    task = _store.get(task_id)
    request = dict(task["request"])
    request["cancel_requested"] = True
    task["request"] = request
    task["status"] = "cancel_requested"
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {"type": "cancel_requested"})
    return {"task_id": task_id, "status": "cancel_requested"}


@router.get("/tasks/{task_id}/control", dependencies=[Depends(_require_admin)])
async def get_task_control(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    task = _store.get(task_id)
    req = task["request"]
    return {
        "task_id": task_id,
        "status": task["status"],
        "cancel_requested": bool(req.get("cancel_requested", False)),
        "lease_expires_at": float(req.get("lease_expires_at", 0.0)),
    }


@router.post("/tasks/{task_id}/result", dependencies=[Depends(_require_admin)])
async def submit_task_result(task_id: str, body: TaskResultBody):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    if body.task_id != task_id:
        raise HTTPException(422, "task_id in path and body must match")
    result = AgentTaskResult(
        **{k: v for k, v in body.model_dump().items() if k not in ("backend", "latency_ms")}
    )
    try:
        result.validate()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    task = _store.get(task_id)
    task["status"] = result.status
    task["result"] = asdict(result)
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {"type": "result_submitted", "status": result.status})

    backend = body.backend or task.get("request", {}).get("backend", "")
    latency_ms = body.latency_ms or int((time.time() - task.get("created_at", time.time())) * 1000)

    post_result_hooks(task, task_id, result.status, backend, latency_ms, body)

    return {"accepted": True, "task_id": task_id, "status": result.status}


@router.post("/tasks/{task_id}/review", dependencies=[Depends(_require_admin)])
async def review_task(task_id: str, body: ReviewBody):
    try:
        return apply_task_review(
            task_id,
            body.decision,
            reviewer=body.reviewer,
            note=body.note,
        )
    except KeyError:
        raise HTTPException(404, "Task not found") from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/tasks/{task_id}/quarantine", dependencies=[Depends(_require_admin)])
async def quarantine_task(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    task = _store.get(task_id)
    task["status"] = "quarantined"
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {"type": "quarantined"})
    return {"task_id": task_id, "status": "quarantined"}


@router.get("/tasks/{task_id}/events", dependencies=[Depends(_require_admin)])
async def get_task_events(task_id: str):
    if not _store.has_events(task_id):
        raise HTTPException(404, "Task not found")
    return {"events": _store.get_events(task_id)}


_create_task_from_body = create_task_from_body
