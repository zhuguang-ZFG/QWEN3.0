"""Session memory schema and SQLite connection."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass


@dataclass
class MemoryEntry:
    id: int
    session_id: str
    timestamp: float
    role: str
    summary: str
    detail: str
    embedding: list[float]
    memory_type: str = "exchange"



_DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DEFAULT_DB_FILE = os.path.join(_DEFAULT_DB_DIR, "lima_sessions.db")
_DB_PATH = os.environ.get("LIMA_SESSION_DB", _DEFAULT_DB_FILE)


def get_db_path() -> str:
    """Resolve the active SQLite path at call time (env, facade patch, or module default)."""
    env_path = os.environ.get("LIMA_SESSION_DB")
    if env_path:
        return env_path
    try:
        import session_memory.store as store_facade

        facade_path = getattr(store_facade, "_DB_PATH", None)
        if isinstance(facade_path, str) and facade_path:
            return facade_path
    except ImportError:
        pass
    return _DB_PATH


def set_db_path(path: str) -> None:
    """Set DB path for runtime/tests; keeps facade and module globals aligned."""
    global _DB_PATH
    _DB_PATH = path
    try:
        import session_memory.store as store_facade

        store_facade._DB_PATH = path
    except ImportError:
        pass


def _get_conn() -> sqlite3.Connection:
    db_path = get_db_path()
    if not os.environ.get("LIMA_SESSION_DB"):
        os.makedirs(os.path.dirname(db_path) or _DEFAULT_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            role TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT DEFAULT '',
            embedding TEXT DEFAULT '[]',
            memory_type TEXT DEFAULT 'exchange'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session
        ON memories(session_id, timestamp DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type
        ON memories(memory_type, timestamp DESC)
    """)
    # Migration: add memory_type column to existing DBs
    try:
        conn.execute("SELECT memory_type FROM memories LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT 'exchange'")
    conn.commit()
    return conn


MEMORY_TYPES = (
    "exchange", "compacted", "project_fact", "code_fact",
    "ops_event", "test_result", "routing_lesson",
    "security_lesson", "reference_pattern", "user_pref",
)


def _sanitize_storage_text(text: str) -> str:
    """Return text safe enough for memory storage without falling back to raw secrets."""
    try:
        from session_memory.redact import sanitize_for_memory

        cleaned = sanitize_for_memory(text)
    except ImportError:
        return text
    if cleaned is None:
        return "[REDACTED]" if text and text.strip() else ""
    return cleaned


def memory_stats() -> dict:
    """Return aggregate statistics about the memory store."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] or 0
    by_type = conn.execute(
        "SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    with_emb = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE embedding != '[]'"
    ).fetchone()[0] or 0
    sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM memories"
    ).fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "with_embeddings": with_emb,
        "embedding_pct": round(with_emb / total * 100, 1) if total else 0,
        "sessions": sessions,
        "by_type": {t: c for t, c in by_type},
    }

