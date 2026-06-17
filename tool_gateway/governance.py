"""Worker governance — registration, heartbeat, and health tracking.

Tracks worker identity, last heartbeat, capacity, and status.
No external dependencies. Persisted to SQLite.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field


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
_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _db_path() -> str:
    return os.environ.get("LIMA_WORKER_DB", os.path.join(_DB_DIR, "worker_registry.db"))


def _get_conn() -> sqlite3.Connection:
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
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
    return conn


def register_worker(worker_id: str, version: str = "", capacity: int = 1) -> WorkerRecord:
    now = time.time()
    rec = WorkerRecord(worker_id=worker_id, registered_at=now, last_heartbeat=now, capacity=capacity, version=version)
    with _lock:
        conn = _get_conn()
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
        conn.commit()
        conn.close()
    return rec


def heartbeat(worker_id: str, status: str = "idle", active_tasks: list[str] | None = None) -> bool:
    now = time.time()
    updates = {"last_heartbeat": now, "status": status}
    if active_tasks is not None:
        updates["active_tasks"] = json.dumps(active_tasks)
    with _lock:
        conn = _get_conn()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [worker_id]
        cur = conn.execute(f"UPDATE workers SET {set_clause} WHERE worker_id = ?", values)
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
    return updated


def get_worker(worker_id: str) -> WorkerRecord | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT worker_id, registered_at, last_heartbeat, status, capacity, "
        "active_tasks, total_completed, total_failed, version "
        "FROM workers WHERE worker_id = ?",
        (worker_id,),
    ).fetchone()
    conn.close()
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
    conn = _get_conn()
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
    conn.close()
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
    conn = _get_conn()
    cur = conn.execute("UPDATE workers SET status = 'quarantined' WHERE worker_id = ?", (worker_id,))
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def mark_offline_stale(timeout_sec: float = 300) -> int:
    """Mark workers offline if no heartbeat within timeout_sec."""
    cutoff = time.time() - timeout_sec
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE workers SET status = 'offline' WHERE status != 'quarantined' AND last_heartbeat < ?",
        (cutoff,),
    )
    conn.commit()
    count = cur.rowcount
    conn.close()
    return count


def reset_for_tests() -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM workers")
    conn.commit()
    conn.close()
