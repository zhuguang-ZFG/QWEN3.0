"""Session Memory store — SQLite-backed cross-request memory.

Stores observations (query summaries, code context) per client session.
Retrieves relevant memories via keyword match + optional semantic search.
Supports progressive disclosure: summary first, expand on demand.
"""

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


def save_memory(
    session_id: str,
    role: str,
    summary: str,
    detail: str = "",
    embedding: list[float] | None = None,
    memory_type: str = "exchange",
) -> int:
    """Save a memory entry. Returns the entry ID."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO memories (session_id, timestamp, role, summary, detail, embedding, memory_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, time.time(), role, summary, detail,
         json.dumps(embedding or []), memory_type),
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def get_recent_memories(
    session_id: str, limit: int = 5
) -> list[MemoryEntry]:
    """Get most recent memories for a session (progressive disclosure: summaries only)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding "
        "FROM memories WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
        )
        for r in rows
    ]


def search_memories_keyword(
    session_id: str, query: str, limit: int = 3
) -> list[MemoryEntry]:
    """Keyword search across session memories."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding "
        "FROM memories WHERE session_id = ? AND summary LIKE ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (session_id, f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
        )
        for r in rows
    ]


def search_memories_semantic(
    session_id: str,
    query_embedding: list[float],
    limit: int = 3,
) -> list[MemoryEntry]:
    """Semantic search using cosine similarity against stored embeddings."""
    import math

    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding "
        "FROM memories WHERE session_id = ? AND embedding != '[]'",
        (session_id,),
    ).fetchall()
    conn.close()

    entries = []
    for r in rows:
        emb = json.loads(r[6])
        if not emb:
            continue
        dot = sum(a * b for a, b in zip(query_embedding, emb))
        norm_a = math.sqrt(sum(x * x for x in query_embedding))
        norm_b = math.sqrt(sum(x * x for x in emb))
        sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        if sim > 0.1:
            entries.append((sim, MemoryEntry(
                id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
                summary=r[4], detail=r[5], embedding=emb,
            )))

    entries.sort(key=lambda x: -x[0])
    return [e for _, e in entries[:limit]]


def count_memories(session_id: str) -> int:
    """Count total memories for a session."""
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]
    conn.close()
    return count


def clear_session(session_id: str) -> int:
    """Delete all memories for a session. Returns count deleted."""
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM memories WHERE session_id = ?", (session_id,)
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


# ── Typed Memory API ─────────────────────────────────────────────────────────

MEMORY_TYPES = (
    "exchange", "compacted", "project_fact", "code_fact",
    "ops_event", "test_result", "routing_lesson",
    "security_lesson", "reference_pattern", "user_pref",
)


def save_typed_memory(
    memory_type: str,
    summary: str,
    detail: str = "",
    session_id: str = "_global",
) -> int:
    """Save a typed memory (not tied to a single exchange)."""
    if memory_type not in MEMORY_TYPES:
        detail = f"[original_type={memory_type}] {detail}".strip()
        memory_type = "project_fact"
    return save_memory(
        session_id=session_id,
        role="system",
        summary=summary,
        detail=detail,
        memory_type=memory_type,
    )


def query_by_type(
    memory_type: str, limit: int = 10, session_id: str | None = None
) -> list[MemoryEntry]:
    """Query memories by type, optionally scoped to a session."""
    conn = _get_conn()
    if session_id:
        rows = conn.execute(
            "SELECT id, session_id, timestamp, role, summary, detail, embedding "
            "FROM memories WHERE memory_type = ? AND session_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (memory_type, session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, session_id, timestamp, role, summary, detail, embedding "
            "FROM memories WHERE memory_type = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (memory_type, limit),
        ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
        )
        for r in rows
    ]
