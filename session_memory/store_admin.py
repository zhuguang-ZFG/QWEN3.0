"""Memory deletion, export gates, and admin helpers."""
from __future__ import annotations

import json
import os
import time

from session_memory.store_db import _get_conn
from session_memory.store_crud import count_memories


# Deletion

def delete_memory(memory_id: int) -> bool:
    """Delete a single memory by ID. Returns True if deleted."""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def delete_memories_by_type(
    memory_type: str,
    session_id: str | None = None,
) -> int:
    """Delete memories by type, optionally scoped to a session. Returns count.
    Requires LIMA_MEMORY_ADMIN=1 for bulk deletion."""
    if not can_delete_memories():
        return 0
    conn = _get_conn()
    if session_id:
        cur = conn.execute(
            "DELETE FROM memories WHERE memory_type = ? AND session_id = ?",
            (memory_type, session_id),
        )
    else:
        cur = conn.execute(
            "DELETE FROM memories WHERE memory_type = ?", (memory_type,)
        )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def delete_memories_older_than(days: int, session_id: str | None = None) -> int:
    """Delete memories older than N days, optionally scoped. Returns count.
    Requires LIMA_MEMORY_ADMIN=1."""
    if not can_delete_memories():
        return 0
    cutoff = time.time() - (days * 86400)
    conn = _get_conn()
    if session_id:
        cur = conn.execute(
            "DELETE FROM memories WHERE timestamp < ? AND session_id = ?",
            (cutoff, session_id),
        )
    else:
        cur = conn.execute(
            "DELETE FROM memories WHERE timestamp < ?", (cutoff,)
        )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


# Export

def _gate_allowed(op: str) -> bool:
    """Check if a memory operation is explicitly allowed."""
    if os.environ.get("LIMA_MEMORY_ADMIN", "0") == "1":
        return True
    return False


def can_export_memories() -> bool:
    return _gate_allowed("export")


def can_delete_memories() -> bool:
    return _gate_allowed("delete")


def export_session_json(session_id: str) -> list[dict]:
    """Export all memories for a session as JSON-serializable dicts.

    Requires LIMA_MEMORY_ADMIN=1 to return actual data. Otherwise returns
    a redacted summary only (count + session_id).
    """
    if not can_export_memories():
        return [{"session_id": session_id, "count": count_memories(session_id), "redacted": True}]

    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    try:
        from session_memory.redact import sanitize_for_display
    except ImportError:
        sanitize_for_display = lambda t: t
    return [
        {
            "id": r[0], "session_id": r[1], "timestamp": r[2],
            "role": r[3], "summary": sanitize_for_display(r[4]),
            "detail": sanitize_for_display(r[5]),
            "embedding": json.loads(r[6]),
            "memory_type": r[7] if len(r) > 7 else "exchange",
        }
        for r in rows
    ]


def export_by_type_json(memory_type: str, limit: int = 100) -> list[dict]:
    """Export memories of a specific type as JSON-serializable dicts.

    Requires LIMA_MEMORY_ADMIN=1 to return actual data.
    """
    if not can_export_memories():
        return [{"memory_type": memory_type, "limit": limit, "redacted": True}]
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE memory_type = ? ORDER BY timestamp DESC LIMIT ?",
        (memory_type, limit),
    ).fetchall()
    conn.close()
    try:
        from session_memory.redact import sanitize_for_display
    except ImportError:
        sanitize_for_display = lambda t: t
    return [
        {
            "id": r[0], "session_id": r[1], "timestamp": r[2],
            "role": r[3], "summary": sanitize_for_display(r[4]),
            "detail": sanitize_for_display(r[5]),
            "embedding": json.loads(r[6]),
            "memory_type": r[7] if len(r) > 7 else "exchange",
        }
        for r in rows
    ]
