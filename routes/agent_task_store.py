"""SQLite-backed agent task store (extracted from agent_tasks)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

_lock = threading.Lock()
_DB_PATH = os.environ.get("LIMA_TASKS_DB", "data/agent_tasks.db")


class TaskStore:
    """SQLite-backed task store with in-memory cache."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY,"
            " request TEXT, status TEXT, created_at REAL, updated_at REAL, result TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " task_id TEXT, event TEXT, ts REAL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id)"
        )
        self._conn.commit()
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        rows = self._conn.execute(
            "SELECT task_id, request, status, created_at, updated_at, result FROM tasks"
        ).fetchall()
        for tid, req, status, created, updated, result in rows:
            task: dict = {
                "request": json.loads(req),
                "status": status,
                "created_at": created,
                "events": [],
            }
            if updated is not None:
                task["updated_at"] = updated
            if result is not None:
                task["result"] = json.loads(result)
            self._cache[tid] = task
        for tid in self._cache:
            evts = self._conn.execute(
                "SELECT event, ts FROM events WHERE task_id=? ORDER BY id", (tid,)
            ).fetchall()
            self._cache[tid]["events"] = [
                {"ts": ts, **json.loads(ev)} for ev, ts in evts
            ]

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
                (
                    task_id,
                    json.dumps(task["request"], ensure_ascii=False),
                    task["status"],
                    task["created_at"],
                    task.get("updated_at"),
                    json.dumps(task["result"], ensure_ascii=False)
                    if "result" in task
                    else None,
                ),
            )
            self._conn.commit()

    def update(self, task_id: str) -> None:
        self.put(task_id, self._cache[task_id])

    def append_event(self, task_id: str, event: dict) -> None:
        ts = time.time()
        self._cache[task_id].setdefault("events", []).append({"ts": ts, **event})
        with _lock:
            self._conn.execute(
                "INSERT INTO events (task_id,event,ts) VALUES(?,?,?)",
                (task_id, json.dumps(event, ensure_ascii=False), ts),
            )
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


_store = TaskStore(_DB_PATH)


def get_task_store() -> TaskStore:
    return _store


def reset_task_store_for_tests() -> None:
    _store.clear_for_tests()
