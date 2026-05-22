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


import tempfile

_DB_PATH = os.environ.get("LIMA_SESSION_DB", os.path.join(tempfile.gettempdir(), "lima_sessions.db"))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            role TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT DEFAULT '',
            embedding TEXT DEFAULT '[]'
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session
        ON memories(session_id, timestamp DESC)
    """)
    conn.commit()
    return conn


def save_memory(
    session_id: str,
    role: str,
    summary: str,
    detail: str = "",
    embedding: list[float] | None = None,
) -> int:
    """Save a memory entry. Returns the entry ID."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO memories (session_id, timestamp, role, summary, detail, embedding) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, time.time(), role, summary, detail,
         json.dumps(embedding or [])),
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
