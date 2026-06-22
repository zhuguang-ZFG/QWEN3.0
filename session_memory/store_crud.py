"""Session memory CRUD and search."""

from __future__ import annotations

import json
import time

from session_memory.store_db import MemoryEntry, _get_conn, _sanitize_storage_text


def save_memory(
    session_id: str,
    role: str,
    summary: str,
    detail: str = "",
    embedding: list[float] | None = None,
    memory_type: str = "exchange",
) -> int:
    """Save a memory entry. Returns the entry ID."""
    summary = _sanitize_storage_text(summary)
    detail = _sanitize_storage_text(detail)

    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO memories (session_id, timestamp, role, summary, detail, embedding, memory_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, time.time(), role, summary, detail, json.dumps(embedding or []), memory_type),
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id or 0


def get_recent_memories(session_id: str, limit: int = 5) -> list[MemoryEntry]:
    """Get most recent memories for a session (progressive disclosure: summaries only)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0],
            session_id=r[1],
            timestamp=r[2],
            role=r[3],
            summary=r[4],
            detail=r[5],
            embedding=json.loads(r[6]),
            memory_type=r[7] if len(r) > 7 else "exchange",
        )
        for r in rows
    ]


def search_memories_keyword(session_id: str, query: str, limit: int = 3) -> list[MemoryEntry]:
    """Keyword search across session memories."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE session_id = ? AND summary LIKE ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (session_id, f"%{query}%", limit),
    ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0],
            session_id=r[1],
            timestamp=r[2],
            role=r[3],
            summary=r[4],
            detail=r[5],
            embedding=json.loads(r[6]),
            memory_type=r[7] if len(r) > 7 else "exchange",
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
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE session_id = ? AND embedding != '[]'",
        (session_id,),
    ).fetchall()
    conn.close()

    entries = []
    for r in rows:
        emb = json.loads(r[6])
        if not emb:
            continue
        if len(query_embedding) != len(emb):
            continue
        dot = sum(a * b for a, b in zip(query_embedding, emb, strict=True))
        norm_a = math.sqrt(sum(x * x for x in query_embedding))
        norm_b = math.sqrt(sum(x * x for x in emb))
        sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        if sim > 0.1:
            entries.append(
                (
                    sim,
                    MemoryEntry(
                        id=r[0],
                        session_id=r[1],
                        timestamp=r[2],
                        role=r[3],
                        summary=r[4],
                        detail=r[5],
                        embedding=emb,
                        memory_type=r[7] if len(r) > 7 else "exchange",
                    ),
                )
            )

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
    cur = conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


# Typed Memory API
#
# Canonical memory taxonomy. Keep in sync with daemon._classify_line().
# Transactional types (exchange, compacted) are internal only and should
# not appear in long-lived typed queries.

MEMORY_TYPES = (
    "exchange",
    "compacted",
    "project_fact",
    "code_fact",
    "ops_event",
    "test_result",
    "routing_lesson",
    "security_lesson",
    "reference_pattern",
    "user_pref",
    "device_draw_failed",
    "device_draw_turn",
)
