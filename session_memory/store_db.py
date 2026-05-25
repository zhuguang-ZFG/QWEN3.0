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
_DB_PATH = os.environ.get("LIMA_SESSION_DB", os.path.join(_DEFAULT_DB_DIR, "lima_sessions.db"))


def _get_conn() -> sqlite3.Connection:
    if not os.environ.get("LIMA_SESSION_DB"):
        os.makedirs(_DEFAULT_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
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

