"""Database connection helpers for the outcome ledger."""

from __future__ import annotations

import os
import sqlite3
import time
import uuid

from session_memory.outcome_ledger.config import get_db_path


def _get_conn() -> sqlite3.Connection:
    """Open the outcome DB, ensure schema/indexes, and return a connection."""
    db_path = get_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            loop TEXT DEFAULT '',
            outcome TEXT NOT NULL DEFAULT 'success',
            backend TEXT DEFAULT '',
            scenario TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            device_id TEXT DEFAULT '',
            request_id TEXT DEFAULT '',
            entrypoint TEXT DEFAULT '',
            fallback_used INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            summary TEXT DEFAULT '',
            details TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            evidence TEXT DEFAULT '[]',
            artifact_paths TEXT DEFAULT '[]',
            rollback TEXT DEFAULT '',
            recorded_at REAL NOT NULL,
            learned INTEGER DEFAULT 0
        )
        """
    )
    for col, col_type in [
        ("loop", "TEXT DEFAULT ''"),
        ("device_id", "TEXT DEFAULT ''"),
        ("request_id", "TEXT DEFAULT ''"),
        ("entrypoint", "TEXT DEFAULT ''"),
        ("fallback_used", "INTEGER DEFAULT 0"),
        ("latency_ms", "INTEGER DEFAULT 0"),
        ("evidence", "TEXT DEFAULT '[]'"),
        ("artifact_paths", "TEXT DEFAULT '[]'"),
        ("rollback", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE outcomes ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_source ON outcomes(source, recorded_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_task ON outcomes(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_loop ON outcomes(loop, outcome)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_unlearned ON outcomes(learned, recorded_at)")
    conn.commit()
    return conn


def _make_id(source: str) -> str:
    return f"{source}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}"
