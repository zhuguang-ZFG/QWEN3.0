"""Agent task business logic (non-route helpers)."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import asdict

from fastapi import HTTPException

from agent_contracts.task_contract import AgentTaskRequest
from agent_evolution.candidates import get_candidate_store
from agent_runtime.prompt_contract import contract_to_dict, resolve_prompt_contract
from routes.agent_task_schemas import TaskCreateBody
_log = logging.getLogger(__name__)


def _store():
    """Use route module store so tests can swap the singleton."""
    from routes import agent_tasks

    return agent_tasks._store
_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


async def require_admin(authorization: str = "") -> None:
    import logging as _log
    from access_guard import (
        configured_api_keys,
        constant_time_equals,
        extract_bearer_token,
    )

    presented = extract_bearer_token(authorization)
    if not presented:
        _log.warning("require_admin: no token presented")
        raise HTTPException(401, "Unauthorized")

    # Accept admin token
    admin_token = get_admin_token()
    if admin_token and constant_time_equals(presented, admin_token):
        _log.info("require_admin: admin token accepted")
        return

    # Accept any configured private API key (enables LiMa Code single-key auth)
    api_keys = configured_api_keys()
    _log.info("require_admin: api_keys=%s, presented=%s...", list(api_keys)[:1], presented[:10])
    if api_keys and any(constant_time_equals(presented, k) for k in api_keys):
        _log.info("require_admin: API key accepted")
        return

    _log.warning("require_admin: token not matched")
    raise HTTPException(401, "Unauthorized")


def task_envelope(task: dict) -> dict:
    envelope = {
        "task": task["request"],
        "status": task["status"],
        "created_at": task["created_at"],
        "events": task.get("events", []),
    }
    if "updated_at" in task:
        envelope["updated_at"] = task["updated_at"]
    if "result" in task:
        envelope["result"] = task["result"]
    return envelope


def task_audit_item(task: dict) -> dict:
    request = task.get("request", {})
    result = task.get("result", {})
    return {
        "task_id": request.get("task_id", ""),
        "status": task.get("status", ""),
        "mode": request.get("mode", ""),
        "repo": request.get("repo", ""),
        "goal": request.get("goal", ""),
        "worker_id": request.get("worker_id", ""),
        "created_at": task.get("created_at", 0),
        "updated_at": task.get("updated_at", task.get("created_at", 0)),
        "event_count": len(task.get("events", [])),
        "changed_files": result.get("changed_files", []),
        "test_commands": result.get("test_commands", []),
        "risks": result.get("risks", []),
        "next_action": result.get("next_action", ""),
    }


def task_counts() -> dict[str, int]:
    store = _store()
    counts = {
        "accepted": 0,
        "running": 0,
        "needs_review": 0,
        "approved": 0,
        "failed": 0,
        "quarantined": 0,
    }
    for task in store.values():
        status = task.get("status", "")
        if status in counts:
            counts[status] += 1
    return counts


def latest_task_id() -> str:
    store = _store()
    tasks = list(store.values())
    if not tasks:
        return ""
    latest = max(tasks, key=lambda t: t.get("updated_at", t.get("created_at", 0)))
    return latest.get("request", {}).get("task_id", "")


def apply_task_review(
    task_id: str,
    decision: str,
    reviewer: str = "human",
    note: str = "",
) -> dict:
    store = _store()
    if not store.contains(task_id):
        raise KeyError("Task not found")
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    task = store.get(task_id)
    if "result" not in task:
        raise RuntimeError("Task has no worker result to review")
    if task["status"] != "needs_review":
        raise RuntimeError(f"Task cannot be reviewed from {task['status']}")
    task["status"] = decision
    task["updated_at"] = time.time()
    store.update(task_id)
    store.append_event(
        task_id,
        {"type": "reviewed", "decision": decision, "reviewer": reviewer, "note": note},
    )
    if decision == "approved":
        try:
            from agent_evolution.candidates import (
                extract_candidate_from_task_evidence,
            )

            candidate = extract_candidate_from_task_evidence(
                task_id=task_id,
                goal=task.get("request", {}).get("goal", ""),
                result=task.get("result", {}),
            )
            get_candidate_store().add(candidate)
            store.append_event(
                task_id,
                {"type": "candidate_created", "skill_id": candidate.skill_id},
            )
        except Exception as exc:
            _log.warning(
                "candidate extract failed task_id=%s err=%s",
                task_id,
                type(exc).__name__,
            )
            store.append_event(
                task_id,
                {"type": "candidate_create_failed", "error": str(exc)[:200]},
            )
    return {"task_id": task_id, "status": decision}


def create_task_from_body(body: TaskCreateBody) -> dict:
    store = _store()
    task_id = str(uuid.uuid4())[:8]
    while store.contains(task_id):
        task_id = str(uuid.uuid4())[:8]
    explicit_contract = (
        body.prompt_contract.model_dump() if body.prompt_contract is not None else None
    )
    try:
        resolved_contract = resolve_prompt_contract(
            goal=body.goal,
            constraints=body.constraints,
            test_commands=body.test_commands,
            mode=body.mode,
            prompt_contract=explicit_contract,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    req = AgentTaskRequest(
        task_id=task_id,
        repo=body.repo,
        branch=body.branch,
        goal=body.goal,
        constraints=body.constraints,
        allowed_tools=body.allowed_tools,
        max_runtime_sec=body.max_runtime_sec,
        mode=body.mode,
        patch_files=body.patch_files,
        test_commands=body.test_commands,
        prompt_contract=contract_to_dict(resolved_contract),
    )
    try:
        req.validate()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    task = {
        "request": asdict(req),
        "status": "accepted",
        "created_at": time.time(),
        "events": [],
    }
    store.put(task_id, task)
    store.append_event(task_id, {"type": "created"})
    return {"task_id": task_id, "status": "accepted"}
