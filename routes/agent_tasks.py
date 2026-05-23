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
    def get_events(self, task_id: str) -> list[dict]:
        return self._cache.get(task_id, {}).get("events", [])
    def has_events(self, task_id: str) -> bool:
        return task_id in self._cache


_store = _TaskStore(_DB_PATH)

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

@router.post("/tasks", dependencies=[Depends(_require_admin)])
async def create_task(body: TaskCreateBody):
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

@router.get("/tasks", dependencies=[Depends(_require_admin)])
async def list_tasks(status: str = Query(default="accepted"),
                     limit: int = Query(default=1, ge=1, le=100)):
    matches = [t for t in _store.values() if not status or t.get("status") == status]
    matches.sort(key=lambda t: t.get("created_at", 0))
    return {"tasks": [t["request"] for t in matches[:limit]], "count": len(matches[:limit])}

@router.get("/tasks/{task_id}", dependencies=[Depends(_require_admin)])
async def get_task(task_id: str):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    return _task_envelope(_store.get(task_id))

@router.post("/tasks/{task_id}/claim", dependencies=[Depends(_require_admin)])
async def claim_task(task_id: str, body: ClaimBody):
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    task = _store.get(task_id)
    if task["status"] not in ("accepted", "claimed", "running"):
        raise HTTPException(409, f"Task cannot be claimed from {task['status']}")
    now = time.time()
    request = dict(task["request"])
    request.update(worker_id=body.worker_id, lease_expires_at=now + body.lease_sec,
                   cancel_requested=False)
    task["request"] = request
    task["status"] = "running"
    task["updated_at"] = now
    _store.update(task_id)
    _store.append_event(task_id, {"type": "claimed", "worker_id": body.worker_id})
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
    if not _store.contains(task_id):
        raise HTTPException(404, "Task not found")
    task = _store.get(task_id)
    if "result" not in task:
        raise HTTPException(409, "Task has no worker result to review")
    if task["status"] != "needs_review":
        raise HTTPException(409, f"Task cannot be reviewed from {task['status']}")
    task["status"] = body.decision
    task["updated_at"] = time.time()
    _store.update(task_id)
    _store.append_event(task_id, {"type": "reviewed", "decision": body.decision,
                                  "reviewer": body.reviewer, "note": body.note})
    return {"task_id": task_id, "status": body.decision}

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