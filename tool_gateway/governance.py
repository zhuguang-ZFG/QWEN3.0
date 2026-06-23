"""Worker governance — registration, heartbeat, and health tracking.

Tracks worker identity, last heartbeat, capacity, and status.
No external dependencies. Persisted to SQLite.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field

from config import settings
from config.sqlite_pool import pooled_sqlite_conn


@dataclass
class WorkerRecord:
    worker_id: str
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "idle"  # idle | busy | offline | quarantined
    capacity: int = 1
    active_tasks: list[str] = field(default_factory=list)
    total_completed: int = 0
    total_failed: int = 0
    version: str = ""


_lock = threading.Lock()


def _db_path() -> str:
    return settings.DB.worker_db


def _ensure_schema(conn) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            registered_at REAL NOT NULL,
            last_heartbeat REAL NOT NULL,
            status TEXT DEFAULT 'idle',
            capacity INTEGER DEFAULT 1,
            active_tasks TEXT DEFAULT '[]',
            total_completed INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0,
            version TEXT DEFAULT ''
        )
    """)


def _prepare_db() -> str:
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    return db_path


def register_worker(worker_id: str, version: str = "", capacity: int = 1) -> WorkerRecord:
    now = time.time()
    rec = WorkerRecord(worker_id=worker_id, registered_at=now, last_heartbeat=now, capacity=capacity, version=version)
    db_path = _prepare_db()
    with _lock, pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO workers (worker_id, registered_at, last_heartbeat, "
            "status, capacity, active_tasks, total_completed, total_failed, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec.worker_id,
                rec.registered_at,
                rec.last_heartbeat,
                rec.status,
                rec.capacity,
                json.dumps(rec.active_tasks),
                rec.total_completed,
                rec.total_failed,
                rec.version,
            ),
        )
    return rec


def heartbeat(worker_id: str, status: str = "idle", active_tasks: list[str] | None = None) -> bool:
    now = time.time()
    updates = {"last_heartbeat": now, "status": status}
    if active_tasks is not None:
        updates["active_tasks"] = json.dumps(active_tasks)
    db_path = _prepare_db()
    with _lock, pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [worker_id]
        cur = conn.execute(f"UPDATE workers SET {set_clause} WHERE worker_id = ?", values)
        updated = cur.rowcount > 0
    return updated


def get_worker(worker_id: str) -> WorkerRecord | None:
    db_path = _prepare_db()
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT worker_id, registered_at, last_heartbeat, status, capacity, "
            "active_tasks, total_completed, total_failed, version "
            "FROM workers WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()
    if not row:
        return None
    return WorkerRecord(
        worker_id=row[0],
        registered_at=row[1],
        last_heartbeat=row[2],
        status=row[3],
        capacity=row[4],
        active_tasks=json.loads(row[5]) if row[5] else [],
        total_completed=row[6],
        total_failed=row[7],
        version=row[8],
    )


def list_workers(status: str = "") -> list[WorkerRecord]:
    db_path = _prepare_db()
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        if status:
            rows = conn.execute(
                "SELECT worker_id, registered_at, last_heartbeat, status, capacity, "
                "active_tasks, total_completed, total_failed, version "
                "FROM workers WHERE status = ? ORDER BY last_heartbeat DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT worker_id, registered_at, last_heartbeat, status, capacity, "
                "active_tasks, total_completed, total_failed, version "
                "FROM workers ORDER BY last_heartbeat DESC"
            ).fetchall()
    return [
        WorkerRecord(
            worker_id=r[0],
            registered_at=r[1],
            last_heartbeat=r[2],
            status=r[3],
            capacity=r[4],
            active_tasks=json.loads(r[5]) if r[5] else [],
            total_completed=r[6],
            total_failed=r[7],
            version=r[8],
        )
        for r in rows
    ]


def quarantine_worker(worker_id: str, reason: str = "") -> bool:
    db_path = _prepare_db()
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        cur = conn.execute("UPDATE workers SET status = 'quarantined' WHERE worker_id = ?", (worker_id,))
        updated = cur.rowcount > 0
    return updated


def mark_offline_stale(timeout_sec: float = 300) -> int:
    """Mark workers offline if no heartbeat within timeout_sec."""
    cutoff = time.time() - timeout_sec
    db_path = _prepare_db()
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "UPDATE workers SET status = 'offline' WHERE status != 'quarantined' AND last_heartbeat < ?",
            (cutoff,),
        )
        count = cur.rowcount
    return count


def reset_for_tests() -> None:
    db_path = _prepare_db()
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        conn.execute("DELETE FROM workers")
