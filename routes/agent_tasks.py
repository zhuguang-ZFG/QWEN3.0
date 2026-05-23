"""Agent task management — SQLite-backed persistence. Validates, persists, returns status."""
import json, os, sqlite3, threading, time, uuid
from dataclasses import asdict
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from agent_contracts.task_contract import AgentTaskRequest, AgentTaskResult
from agent_evolution.candidates import get_candidate_store
from agent_evolution.promote import promote_candidate

router = APIRouter(prefix="/agent")
_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")
_DB_PATH = os.environ.get("LIMA_TASKS_DB", "data/agent_tasks.db")
_lock = threading.Lock()


def _get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN

async def _require_admin(authorization: str = Header(default="")) -> None:
    token_expected = _get_admin_token()
    if not token_expected:
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    token = authorization.replace("Bearer ", "").strip()
    if token != token_expected:
        raise HTTPException(401, "Unauthorized")

class _TaskStore:
    """SQLite-backed task store with in-memory cache."""
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY,"
            " request TEXT, status TEXT, created_at REAL, updated_at REAL, result TEXT)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " task_id TEXT, event TEXT, ts REAL)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id)")
        self._conn.commit()
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        rows = self._conn.execute(
            "SELECT task_id, request, status, created_at, updated_at, result FROM tasks"
        ).fetchall()
        for tid, req, status, created, updated, result in rows:
            t: dict = {"request": json.loads(req), "status": status,
                       "created_at": created, "events": []}
            if updated is not None:
                t["updated_at"] = updated
            if result is not None:
                t["result"] = json.loads(result)
            self._cache[tid] = t
        for tid in self._cache:
            evts = self._conn.execute(
                "SELECT event, ts FROM events WHERE task_id=? ORDER BY id", (tid,)
            ).fetchall()
            self._cache[tid]["events"] = [{"ts": ts, **json.loads(ev)} for ev, ts in evts]

    def contains(self, task_id: str) -> bool:
        return task_id in self._cache
    def get(self, task_id: str) -> dict:
        return self._cache[task_id]
    def values(self):
        return self._cache.values()

    def put(self, task_id: str, task: dict) -> None:
        self._cache[task_id] = task
        with _lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks"
                " (task_id,request,status,created_at,updated_at,result) VALUES(?,?,?,?,?,?)",
                (task_id, json.dumps(task["request"], ensure_ascii=False), task["status"],
                 task["created_at"], task.get("updated_at"),
                 json.dumps(task["result"], ensure_ascii=False) if "result" in task else None))
            self._conn.commit()
    def update(self, task_id: str) -> None:
        self.put(task_id, self._cache[task_id])
    def append_event(self, task_id: str, event: dict) -> None:
        ts = time.time()
        self._cache[task_id].setdefault("events", []).append({"ts": ts, **event})
        with _lock:
            self._conn.execute(
                "INSERT INTO events (task_id,event,ts) VALUES(?,?,?)",
                (task_id, json.dumps(event, ensure_ascii=False), ts))
            self._conn.commit()
    def claim(self, task_id: str, worker_id: str, lease_sec: int) -> dict:
        now = time.time()
        with _lock:
            task = self._cache[task_id]
            request = dict(task["request"])
            lease_expires_at = float(request.get("lease_expires_at") or 0.0)
            if task["status"] not in ("accepted", "claimed", "running"):
                raise ValueError(f"Task cannot be claimed from {task['status']}")
            if task["status"] in ("claimed", "running") and lease_expires_at > now:
                raise RuntimeError("Task already has an active lease")
            request.update(
                worker_id=worker_id,
                lease_expires_at=now + lease_sec,
                cancel_requested=False,
            )
            task["request"] = request
            task["status"] = "running"
            task["updated_at"] = now
            self._conn.execute(
                "UPDATE tasks SET request=?, status=?, updated_at=? WHERE task_id=?",
                (json.dumps(request, ensure_ascii=False), "running", now, task_id),
            )
            event = {"type": "claimed", "worker_id": worker_id}
            task.setdefault("events", []).append({"ts": now, **event})
            self._conn.execute(
                "INSERT INTO events (task_id,event,ts) VALUES(?,?,?)",
                (task_id, json.dumps(event, ensure_ascii=False), now),
            )
            self._conn.commit()
            return task
    def get_events(self, task_id: str) -> list[dict]:
        return self._cache.get(task_id, {}).get("events", [])
    def has_events(self, task_id: str) -> bool:
        return task_id in self._cache
    def clear_for_tests(self) -> None:
        with _lock:
            self._conn.execute("DELETE FROM events")
            self._conn.execute("DELETE FROM tasks")
            self._conn.commit()
            self._cache.clear()


_store = _TaskStore(_DB_PATH)


def _reset_for_tests() -> None:
    _store.clear_for_tests()

# --- Pydantic models ---
class TaskCreateBody(BaseModel):
    repo: str
    branch: str = "main"
    goal: str
    constraints: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    max_runtime_sec: int = 300
    mode: Literal["plan", "patch", "test", "review"] = "patch"
    patch_files: list[dict] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)


class WorkerSmokeTaskBody(BaseModel):
    repo: str
    branch: str = "main"
    kind: Literal["review", "patch_readme"] = "review"


class TaskResultBody(BaseModel):
    task_id: str
    status: Literal["accepted", "claimed", "running", "needs_review", "approved",
                    "rejected", "applied", "succeeded", "failed", "blocked",
                    "cancel_requested", "cancelled", "quarantined"]
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    test_results: list[dict] = Field(default_factory=list)
    diff_preview: str = ""
    artifacts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_action: str = ""

class ClaimBody(BaseModel):
    worker_id: str
    lease_sec: int = Field(default=300, ge=1, le=3600)

class ReviewBody(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = "human"
    note: str = ""

class PromoteBody(BaseModel):
    eval_passed: bool = False
    manual_flag: bool = False

# --- Helpers ---
def _task_envelope(task: dict) -> dict:
    envelope = {"task": task["request"], "status": task["status"],
                "created_at": task["created_at"], "events": task.get("events", [])}
    if "updated_at" in task:
        envelope["updated_at"] = task["updated_at"]
    if "result" in task:
        envelope["result"] = task["result"]
    return envelope


def _task_audit_item(task: dict) -> dict:
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


def _task_counts() -> dict[str, int]:
    counts = {
        "accepted": 0,
        "running": 0,
        "needs_review": 0,
        "approved": 0,
        "failed": 0,
        "quarantined": 0,
    }
    for task in _store.values():
        status = task.get("status", "")
        if status in counts:
            counts[status] += 1
    return counts


def _latest_task_id() -> str:
    tasks = list(_store.values())
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
    if not _store.contains(task_id):
        raise KeyError("Task not found")
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    task = _store.get(task_id)
    if "result" not in task:
        raise RuntimeError("Task has no worker result to review")
    if task["status"] != "needs_review":
        raise RuntimeError(f"Task cannot be reviewed from {task['status']}")
    task["status"] = decision
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {
        "type": "reviewed",
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
    })
    if decision == "approved":
        try:
            from agent_evolution.candidates import (
                extract_candidate_from_task_evidence,
                get_candidate_store,
            )
            candidate = extract_candidate_from_task_evidence(
                task_id=task_id,
                goal=task.get("request", {}).get("goal", ""),
                result=task.get("result", {}),
            )
            get_candidate_store().add(candidate)
            _store.append_event(task_id, {
                "type": "candidate_created",
                "skill_id": candidate.skill_id,
            })
        except Exception as exc:
            _store.append_event(task_id, {
                "type": "candidate_create_failed",
                "error": str(exc)[:200],
            })
    return {"task_id": task_id, "status": decision}


def _create_task_from_body(body: TaskCreateBody) -> dict:
    task_id = str(uuid.uuid4())[:8]
    while _store.contains(task_id):
        task_id = str(uuid.uuid4())[:8]
    req = AgentTaskRequest(
        task_id=task_id, repo=body.repo, branch=body.branch,
        goal=body.goal, constraints=body.constraints,
        allowed_tools=body.allowed_tools, max_runtime_sec=body.max_runtime_sec,
        mode=body.mode, patch_files=body.patch_files, test_commands=body.test_commands)
    try:
        req.validate()
    except ValueError as e:
        raise HTTPException(422, str(e))
    task = {"request": asdict(req), "status": "accepted",
            "created_at": time.time(), "events": []}
    _store.put(task_id, task)
    _store.append_event(task_id, {"type": "created"})
    return {"task_id": task_id, "status": "accepted"}


@router.post("/tasks", dependencies=[Depends(_require_admin)])
async def create_task(body: TaskCreateBody):
    return _create_task_from_body(body)

@router.get("/tasks", dependencies=[Depends(_require_admin)])
async def list_tasks(status: str = Query(default="accepted"),
                     limit: int = Query(default=1, ge=1, le=100)):
    matches = [t for t in _store.values() if not status or t.get("status") == status]
    matches.sort(key=lambda t: t.get("created_at", 0))
    return {"tasks": [t["request"] for t in matches[:limit]], "count": len(matches[:limit])}


@router.get("/audit", dependencies=[Depends(_require_admin)])
async def agent_audit(limit: int = Query(default=20, ge=1, le=100)):
    tasks = list(_store.values())
    tasks.sort(
        key=lambda t: t.get("updated_at", t.get("created_at", 0)),
        reverse=True,
    )
    items = [_task_audit_item(task) for task in tasks[:limit]]
    return {"tasks": items, "count": len(items)}


@router.get("/worker/preflight", dependencies=[Depends(_require_admin)])
async def worker_preflight():
    return {
        "ready": True,
        "contract_version": "agent-task-v1",
        "server_time": time.time(),
        "counts": _task_counts(),
        "latest_task_id": _latest_task_id(),
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
            patch_files=[{
                "file_path": "README.md",
                "content": "# LiMa Code Smoke\n",
            }],
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
    return _create_task_from_body(task)


@router.get("/tasks/{task_id}", dependencies=[Depends(_require_admin)])
async def get_task(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    return _task_envelope(_store.get(task_id))

@router.post("/tasks/{task_id}/claim", dependencies=[Depends(_require_admin)])
async def claim_task(task_id: str, body: ClaimBody):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    try:
        task = _store.claim(task_id, body.worker_id, body.lease_sec)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return _task_envelope(task)

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
    return {"task_id": task_id, "status": task["status"],
            "cancel_requested": bool(req.get("cancel_requested", False)),
            "lease_expires_at": float(req.get("lease_expires_at", 0.0))}

@router.post("/tasks/{task_id}/result", dependencies=[Depends(_require_admin)])
async def submit_task_result(task_id: str, body: TaskResultBody):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    if body.task_id != task_id:
        raise HTTPException(422, "task_id in path and body must match")
    result = AgentTaskResult(**body.model_dump())
    try:
        result.validate()
    except ValueError as e:
        raise HTTPException(422, str(e))
    task = _store.get(task_id)
    task["status"] = result.status
    task["result"] = asdict(result)
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {"type": "result_submitted", "status": result.status})
    if result.status == "needs_review":
        try:
            from telegram_notify import notify_task_ready
            notify_task_ready(task_id, body.summary, body.changed_files)
        except Exception:
            pass
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
        raise HTTPException(404, "Task not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))

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

@router.get("/skills/candidates", dependencies=[Depends(_require_admin)])
async def list_skill_candidates():
    store = get_candidate_store()
    return {"candidates": [asdict(c) for c in store.list_pending()]}

@router.post("/skills/{skill_id}/promote", dependencies=[Depends(_require_admin)])
async def promote_skill(skill_id: str, body: PromoteBody):
    store = get_candidate_store()
    success = promote_candidate(store, skill_id, body.eval_passed, body.manual_flag)
    if not success:
        raise HTTPException(400, "Promotion failed: eval must pass and manual flag required")
    return {"promoted": True, "skill_id": skill_id}
