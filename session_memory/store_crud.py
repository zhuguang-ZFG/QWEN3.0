"""Session memory CRUD and search."""
from __future__ import annotations

import json
import math
import time

from session_memory.store_db import MemoryEntry, _get_conn, _sanitize_storage_text

# ── Decay configuration ────────────────────────────────────────────────
_HALF_LIFE_HOURS = 168.0   # 1 week half-life for recall decay
_DECAY_FLOOR = 0.3          # memories never drop below 30% weight
_BOOST_LOG_FACTOR = 0.15    # log(1+recall_count) multiplier


def _decay_weight(recall_count: int, last_recalled_at: float) -> float:
    """Compute recall-weighted decay score for a memory.

    decay = max(floor, 0.5 ^ (hours_since_last_recall / half_life))
    boost = 1 + factor * ln(1 + recall_count)
    weight = decay * boost
    """
    if last_recalled_at <= 0:
        decay = 1.0  # never recalled → full weight (no decay)
    else:
        hours_ago = (time.time() - last_recalled_at) / 3600.0
        decay = max(_DECAY_FLOOR, 0.5 ** (hours_ago / _HALF_LIFE_HOURS))
    boost = 1.0 + _BOOST_LOG_FACTOR * math.log(1 + recall_count)
    return round(decay * boost, 4)


def _bump_recall(memory_ids: list[int]) -> None:
    """Increment recall_count and update last_recalled_at for given memory IDs."""
    if not memory_ids:
        return
    conn = _get_conn()
    now = time.time()
    placeholders = ",".join("?" * len(memory_ids))
    conn.execute(
        f"UPDATE memories SET recall_count = recall_count + 1, last_recalled_at = ? "
        f"WHERE id IN ({placeholders})",
        [now] + list(memory_ids),
    )
    conn.commit()
    conn.close()


_ROW_SQL = (
    "SELECT id, session_id, timestamp, role, summary, detail, embedding, "
    "memory_type, recall_count, last_recalled_at FROM memories"
)


def _row_to_entry(row: tuple) -> MemoryEntry:
    """Convert a DB row tuple (10 fields) to MemoryEntry."""
    return MemoryEntry(
        id=row[0], session_id=row[1], timestamp=row[2], role=row[3],
        summary=row[4], detail=row[5], embedding=json.loads(row[6]),
        memory_type=row[7] if len(row) > 7 else "exchange",
        recall_count=row[8] if len(row) > 8 else 0,
        last_recalled_at=row[9] if len(row) > 9 else 0.0,
    )

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
    return entry_id or 0


def get_recent_memories(
    session_id: str, limit: int = 5
) -> list[MemoryEntry]:
    """Get most recent memories for a session, sorted by decay-weighted recency."""
    conn = _get_conn()
    rows = conn.execute(
        f"{_ROW_SQL} WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    entries = [_row_to_entry(r) for r in rows]
    # Sort by decay weight (boosts frequently-recalled memories)
    entries.sort(key=lambda e: _decay_weight(e.recall_count, e.last_recalled_at), reverse=True)
    if entries:
        _bump_recall([e.id for e in entries])
    return entries


def search_memories_keyword(
    session_id: str, query: str, limit: int = 3
) -> list[MemoryEntry]:
    """Keyword search across session memories, sorted by decay-weighted match."""
    conn = _get_conn()
    rows = conn.execute(
        f"{_ROW_SQL} WHERE session_id = ? AND summary LIKE ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (session_id, f"%{query}%", limit),
    ).fetchall()
    conn.close()
    entries = [_row_to_entry(r) for r in rows]
    entries.sort(key=lambda e: _decay_weight(e.recall_count, e.last_recalled_at), reverse=True)
    if entries:
        _bump_recall([e.id for e in entries])
    return entries


def search_memories_semantic(
    session_id: str,
    query_embedding: list[float],
    limit: int = 3,
) -> list[MemoryEntry]:
    """Semantic search using cosine similarity × decay weight."""
    conn = _get_conn()
    rows = conn.execute(
        f"{_ROW_SQL} WHERE session_id = ? AND embedding != '[]'",
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
            entry = _row_to_entry(r)
            # Weighted score: similarity × decay boost
            weight = _decay_weight(entry.recall_count, entry.last_recalled_at)
            entries.append((sim * weight, entry))

    entries.sort(key=lambda x: -x[0])
    result = [e for _, e in entries[:limit]]
    if result:
        _bump_recall([e.id for e in result])
    return result


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
#
# Canonical memory taxonomy. Keep in sync with daemon._classify_line().
# Transactional types (exchange, compacted) are internal only and should
# not appear in long-lived typed queries.

MEMORY_TYPES = (
    "exchange", "compacted", "project_fact", "code_fact",
    "ops_event", "test_result", "routing_lesson",
    "security_lesson", "reference_pattern", "user_pref",
)

