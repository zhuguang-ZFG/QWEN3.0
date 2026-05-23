"""Agent task management endpoints.

Server only validates, persists, and returns status.
It does NOT run shell commands or execute tasks directly.
"""

import os
import time
import uuid
from dataclasses import asdict

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from agent_contracts.task_contract import AgentTaskRequest
from agent_evolution.candidates import get_candidate_store
from agent_evolution.promote import promote_candidate

router = APIRouter(prefix="/agent")

_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def _get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


async def _require_admin(authorization: str = Header(default="")) -> None:
    token_expected = _get_admin_token()
    if not token_expected:
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    token = authorization.replace("Bearer ", "").strip()
    if token != token_expected:
        raise HTTPException(401, "Unauthorized")


# In-memory task store (production would use SQLite/Redis)
_tasks: dict[str, dict] = {}
_events: dict[str, list[dict]] = {}


class TaskCreateBody(BaseModel):
    repo: str
    branch: str = "main"
    goal: str
    constraints: list[str] = []
    allowed_tools: list[str] = []
    max_runtime_sec: int = 300
    mode: Literal["plan", "patch", "test", "review"] = "patch"


class PromoteBody(BaseModel):
    eval_passed: bool = False
    manual_flag: bool = False


@router.post("/tasks", dependencies=[Depends(_require_admin)])
async def create_task(body: TaskCreateBody):
    """Create a new agent task. Does NOT execute it."""
    task_id = str(uuid.uuid4())[:8]
    while task_id in _tasks:
        task_id = str(uuid.uuid4())[:8]
    req = AgentTaskRequest(
        task_id=task_id, repo=body.repo, branch=body.branch,
        goal=body.goal, constraints=body.constraints,
        allowed_tools=body.allowed_tools,
        max_runtime_sec=body.max_runtime_sec, mode=body.mode,
    )
    try:
        req.validate()
    except ValueError as e:
        raise HTTPException(422, str(e))
    _tasks[task_id] = {
        "request": asdict(req), "status": "accepted",
        "created_at": time.time(), "events": [],
    }
    _events[task_id] = [{"type": "created", "ts": time.time()}]
    return {"task_id": task_id, "status": "accepted"}


@router.get("/tasks/{task_id}", dependencies=[Depends(_require_admin)])
async def get_task(task_id: str):
    """Get task status and details."""
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    return _tasks[task_id]


@router.get("/tasks/{task_id}/events", dependencies=[Depends(_require_admin)])
async def get_task_events(task_id: str):
    """Get task event stream."""
    if task_id not in _events:
        raise HTTPException(404, "Task not found")
    return {"events": _events[task_id]}


@router.get("/skills/candidates", dependencies=[Depends(_require_admin)])
async def list_skill_candidates():
    """List pending skill candidates awaiting promotion."""
    store = get_candidate_store()
    pending = store.list_pending()
    return {"candidates": [asdict(c) for c in pending]}


@router.post("/skills/{skill_id}/promote", dependencies=[Depends(_require_admin)])
async def promote_skill(skill_id: str, body: PromoteBody):
    """Promote a skill candidate (requires eval + manual flag)."""
    store = get_candidate_store()
    success = promote_candidate(
        store, skill_id, body.eval_passed, body.manual_flag)
    if not success:
        raise HTTPException(
            400, "Promotion failed: eval must pass and manual flag required")
    return {"promoted": True, "skill_id": skill_id}
