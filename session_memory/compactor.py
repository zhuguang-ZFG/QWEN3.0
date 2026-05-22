"""Session memory compactor — LLM-driven summarization of old memories.

Based on Google ADK Context Compaction + claude-mem AI Summarization:
- When session memories exceed threshold, compress oldest entries
- Sliding window: take oldest N → summarize into 1 → replace
- Keep recent entries uncompressed (progressive disclosure)
- Use LiMa's own free backends for summarization
"""

import time
from session_memory.store import (
    MemoryEntry,
    get_recent_memories,
    save_memory,
    count_memories,
    _get_conn,
)


COMPACTION_THRESHOLD = 20
COMPACTION_BATCH = 10
KEEP_RECENT = 5


def needs_compaction(session_id: str) -> bool:
    """Check if a session needs memory compaction."""
    return count_memories(session_id) > COMPACTION_THRESHOLD


def get_oldest_memories(session_id: str, limit: int = 10) -> list[MemoryEntry]:
    """Get oldest memories for compaction."""
    import json
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, session_id, timestamp, role, summary, detail, embedding "
        "FROM memories WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
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


def _delete_memories_by_ids(ids: list[int]) -> int:
    """Delete memories by their IDs."""
    if not ids:
        return 0
    conn = _get_conn()
    placeholders = ",".join("?" * len(ids))
    cur = conn.execute(
        f"DELETE FROM memories WHERE id IN ({placeholders})", ids
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


def compact_session(session_id: str, summarizer=None) -> dict:
    """Compact oldest memories into a single summary.

    Args:
        session_id: The session to compact
        summarizer: Optional callable(list[str]) -> str that generates a summary.
                    If None, uses simple concatenation fallback.

    Returns:
        dict with compaction stats (before, after, compressed_count)
    """
    if not needs_compaction(session_id):
        return {"compacted": False, "reason": "below threshold"}

    before_count = count_memories(session_id)
    oldest = get_oldest_memories(session_id, limit=COMPACTION_BATCH)

    if len(oldest) < 2:
        return {"compacted": False, "reason": "not enough memories"}

    summaries = [m.summary for m in oldest]

    if summarizer:
        try:
            compressed = summarizer(summaries)
        except Exception:
            compressed = _fallback_summarize(summaries)
    else:
        compressed = _fallback_summarize(summaries)

    ids_to_delete = [m.id for m in oldest]
    _delete_memories_by_ids(ids_to_delete)

    save_memory(
        session_id=session_id,
        role="compacted",
        summary=f"[压缩摘要] {compressed}",
        detail="\n".join(summaries),
    )

    after_count = count_memories(session_id)
    return {
        "compacted": True,
        "before": before_count,
        "after": after_count,
        "compressed_count": len(ids_to_delete),
    }


def _fallback_summarize(summaries: list[str]) -> str:
    """Simple fallback: extract key terms from summaries."""
    all_text = " | ".join(s[:50] for s in summaries)
    return all_text[:200]


def llm_summarizer_factory(call_fn):
    """Create an LLM-based summarizer using LiMa's own backends.

    Args:
        call_fn: async callable(messages) -> str that calls a LiMa backend

    Returns:
        A synchronous summarizer function for compact_session()
    """
    import asyncio

    def summarizer(summaries: list[str]) -> str:
        prompt = (
            "将以下对话摘要压缩为一句话（中文，不超过100字）：\n"
            + "\n".join(f"- {s}" for s in summaries)
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, call_fn(messages)).result()
            else:
                result = asyncio.run(call_fn(messages))
            return result[:200] if result else _fallback_summarize(summaries)
        except Exception:
            return _fallback_summarize(summaries)

    return summarizer
