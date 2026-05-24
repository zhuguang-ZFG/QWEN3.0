"""Session Memory store - SQLite-backed cross-request memory.

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
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
            memory_type=r[7] if len(r) > 7 else "exchange",
        )
        for r in rows
    ]


def search_memories_keyword(
    session_id: str, query: str, limit: int = 3
) -> list[MemoryEntry]:
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
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
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
        dot = sum(a * b for a, b in zip(query_embedding, emb))
        norm_a = math.sqrt(sum(x * x for x in query_embedding))
        norm_b = math.sqrt(sum(x * x for x in emb))
        sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        if sim > 0.1:
            entries.append((sim, MemoryEntry(
                id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
                summary=r[4], detail=r[5], embedding=emb,
                memory_type=r[7] if len(r) > 7 else "exchange",
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


# Typed Memory API

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
            "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
            "FROM memories WHERE memory_type = ? AND session_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (memory_type, session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
            "FROM memories WHERE memory_type = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (memory_type, limit),
        ).fetchall()
    conn.close()
    return [
        MemoryEntry(
            id=r[0], session_id=r[1], timestamp=r[2], role=r[3],
            summary=r[4], detail=r[5], embedding=json.loads(r[6]),
            memory_type=r[7] if len(r) > 7 else "exchange",
        )
        for r in rows
    ]


# Promotion

_PROMOTION_RULES: dict[str, dict[str, list[str]]] = {
    "exchange": {
        "reference_pattern": ["pattern", "reference", "reusable"],
        "routing_lesson": ["route", "backend", "fallback"],
        "code_fact": ["def ", "class ", "import "],
        "ops_event": ["deploy", "restart", "server"],
        "test_result": ["test", "passed", "failed", "coverage"],
        "security_lesson": ["vuln", "auth", "token", "secret"],
        "user_pref": ["prefer", "user", "style"],
    },
}


def promote_memory(
    memory_id: int,
    new_type: str,
    evidence: str = "",
    auto: bool = False,
) -> bool:
    """Promote a memory from one type to another with evidence.

    Returns True if promotion succeeded, False if rejected.
    """
    if new_type not in MEMORY_TYPES or new_type == "exchange":
        return False

    conn = _get_conn()
    row = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding, memory_type "
        "FROM memories WHERE id = ?", (memory_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False

    old_type = row[7] if len(row) > 7 else "exchange"
    detail = row[5] or ""
    evidence = _sanitize_storage_text(evidence)
    evidence_line = f"[promoted from {old_type}]" + (f" evidence={evidence}" if evidence else "")
    new_detail = f"{evidence_line}\n{detail}" if detail else evidence_line

    conn.execute(
        "UPDATE memories SET memory_type = ?, detail = ? WHERE id = ?",
        (new_type, new_detail, memory_id),
    )
    conn.commit()
    conn.close()
    _record_promotion_audit(memory_id, old_type, new_type, evidence, auto)
    return True


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


def auto_promote_candidates(session_id: str, limit: int = 50) -> list[int]:
    """Find exchange memories that match promotion rule keywords.

    Returns list of memory IDs that are candidates for promotion.
    Does NOT perform the promotion - caller decides.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, summary FROM memories "
        "WHERE session_id = ? AND memory_type = 'exchange' "
        "ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()

    candidates = []
    for mem_id, summary in rows:
        text = (summary or "").lower()
        for new_type, rule_set in _PROMOTION_RULES.get("exchange", {}).items():
            for keywords in [rule_set]:
                if any(kw in text for kw in keywords):
                    if mem_id not in candidates:
                        candidates.append(mem_id)
    return candidates


def _record_promotion_audit(
    memory_id: int, old_type: str, new_type: str,
    evidence: str, auto: bool,
) -> None:
    """Record promotion in audit log (lightweight JSONL)."""
    audit_dir = os.path.dirname(_DB_PATH)
    audit_path = os.path.join(audit_dir, "memory_promotions.jsonl")
    try:
        entry = {
            "memory_id": memory_id, "old_type": old_type,
            "new_type": new_type, "evidence": evidence,
            "auto": auto, "timestamp": time.time(),
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


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
    """Delete memories by type, optionally scoped to a session. Returns count."""
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
    """Delete memories older than N days, optionally scoped. Returns count."""
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

def export_session_json(session_id: str) -> list[dict]:
    """Export all memories for a session as JSON-serializable dicts."""
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
    """Export memories of a specific type as JSON-serializable dicts."""
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
