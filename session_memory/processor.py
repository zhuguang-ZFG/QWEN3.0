"""Session memory processor for context_pipeline integration.

Six-tier recall cascade:
  Tier 1: keyword (SQL LIKE, fast local)
  Tier 2: ChromaDB semantic (local, zero API dependency)
  Tier 3: Jina AI semantic (external, fallback)
  Tier 4: cross-session global + recent
  Tier 5: Outcome Ledger routing lessons
  Tier 6: typed memories (code_fact, routing_lesson, reference_pattern)
"""

import hashlib
import logging
import os

from context_pipeline import RequestContext
from session_memory.store import (
    get_recent_memories,
    search_memories_keyword,
)

_log = logging.getLogger(__name__)


def _session_id_from_headers(headers: dict) -> str:
    """Derive session ID from request headers.

    Priority:
    1. x-lima-user-id header (explicit cross-device identity bridge)
    2. IP + User-Agent hash (implicit fingerprint)
    """
    user_id = headers.get("x-lima-user-id", "").strip()
    if user_id:
        return hashlib.sha256(f"uid:{user_id}".encode()).hexdigest()[:16]
    ip = headers.get("x-forwarded-for", headers.get("x-real-ip", "unknown"))
    ua = headers.get("user-agent", "")
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _chroma_semantic_search(session_id: str, query: str, limit: int = 3) -> list:
    """Tier 2: ChromaDB semantic search (local, zero API dependency)."""
    try:
        from session_memory.chroma_store import search_memory

        results = search_memory(session_id, query, limit=limit)
        if not results:
            return []

        # Map ChromaDB results back to MemoryEntry via SQLite
        from session_memory.store_db import _get_conn, MemoryEntry
        import json

        ids = [r["sqlite_id"] for r in results if r["sqlite_id"] > 0]
        if not ids:
            return []

        conn = _get_conn()
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, session_id, timestamp, role, summary, detail, embedding, "
            f"memory_type, recall_count, last_recalled_at FROM memories WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        conn.close()

        entries = []
        for row in rows:
            entries.append(MemoryEntry(
                id=row[0], session_id=row[1], timestamp=row[2], role=row[3],
                summary=row[4], detail=row[5], embedding=json.loads(row[6]),
                memory_type=row[7] if len(row) > 7 else "exchange",
                recall_count=row[8] if len(row) > 8 else 0,
                last_recalled_at=row[9] if len(row) > 9 else 0.0,
            ))
        return entries
    except ImportError:
        _log.debug("ChromaDB semantic search not available")
    except Exception:
        _log.debug("ChromaDB semantic search failed", exc_info=True)
    return []


def _semantic_fallback(session_id: str, query: str, limit: int = 3) -> list:
    """Tier 3: Jina AI embeddings + SQLite cosine similarity (external API fallback)."""
    try:
        from code_context.embedding_client import get_embeddings

        emb = get_embeddings([query[:2000]], dimensions=128)
        if not emb or not emb[0]:
            return []
        from session_memory.store import search_memories_semantic

        return search_memories_semantic(session_id, emb[0], limit=limit)
    except ImportError:
        _log.debug("Jina semantic search not available")
    except Exception:
        _log.debug("Jina semantic search failed", exc_info=True)
    return []


def _cross_session_fallback(query: str, limit: int = 2) -> list:
    """Search global (cross-session) memories when per-session misses."""
    try:
        return search_memories_keyword("_global", query[:50], limit=limit)
    except Exception:
        return []


def _outcome_recall(query: str, limit: int = 2) -> list[str]:
    """Tier 5: Outcome Ledger routing lessons — backend success patterns."""
    try:
        from session_memory.outcome_ledger import query as ledger_query

        events = ledger_query(limit=50)
        if not events:
            return []

        # Extract query keywords for simple matching
        q_lower = query.lower()
        keywords = []
        for kw in ["code", "debug", "refactor", "test", "deploy", "api", "fix", "optimize"]:
            if kw in q_lower:
                keywords.append(kw)

        # Score events by relevance to current query + outcome
        lessons: list[tuple[float, str]] = []
        for e in events:
            summary = (e.get("summary", "") or "").lower()
            score = 0.0
            for kw in keywords:
                if kw in summary:
                    score += 0.3
            if e.get("outcome") == "success":
                score += 0.1
            backend = e.get("backend", "")
            if backend and backend in q_lower:
                score += 0.5
            if score > 0.2:
                lessons.append((score, f"- [routing_lesson] backend={e.get('backend','?')} outcome={e.get('outcome','?')} {e.get('summary','')[:120]}"))

        lessons.sort(key=lambda x: -x[0])
        return [text for _, text in lessons[:limit]]
    except ImportError:
        _log.debug("Outcome Ledger not available")
    except Exception:
        _log.debug("Outcome recall failed", exc_info=True)
    return []


def _inject_memory_prompt(memories: list, ctx: RequestContext) -> list[int]:
    """Format memory entries into system prompt. Returns list of recalled IDs."""
    recalled_ids: list[int] = []
    if not memories:
        return recalled_ids

    lines = ["[session memory]"]
    for m in memories:
        recalled_ids.append(m.id)
        lines.append(f"- [{m.role}] {m.summary}")
    memory_text = "\n".join(lines)[:600]

    if ctx.system_prompt:
        ctx.system_prompt += "\n\n" + memory_text
    else:
        ctx.system_prompt = memory_text

    return recalled_ids


def _inject_outcome_lessons(lessons: list[str], ctx: RequestContext) -> None:
    """Append Outcome Ledger routing lessons to system prompt."""
    if not lessons:
        return
    text = "[routing lessons from past outcomes]\n" + "\n".join(lessons)
    if ctx.system_prompt:
        ctx.system_prompt += "\n\n" + text[:600]
    else:
        ctx.system_prompt = text[:600]


def session_memory_processor(ctx: RequestContext) -> RequestContext:
    """Pipeline processor: inject relevant session memories into context."""
    if os.environ.get("LIMA_SESSION_MEMORY", "0") != "1":
        return ctx

    session_id = _session_id_from_headers(ctx.headers)

    query = ""
    for msg in reversed(ctx.messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            query = msg["content"]
            break

    if not query:
        return ctx

    # Tier 1: keyword search (fast, no external API)
    memories = search_memories_keyword(session_id, query[:50], limit=3)

    # Tier 2: ChromaDB semantic search (local, zero API dependency)
    if not memories:
        memories = _chroma_semantic_search(session_id, query, limit=3)

    # Tier 3: Jina AI semantic search (external, fallback)
    if not memories:
        memories = _semantic_fallback(session_id, query, limit=3)

    # Tier 4: cross-session global + recent
    if not memories:
        cross = _cross_session_fallback(query, limit=2)
        memories = cross
    if not memories:
        memories = get_recent_memories(session_id, limit=2)

    recalled_ids = _inject_memory_prompt(memories, ctx)

    # Tier 5: Outcome Ledger routing lessons (always inject, separate from memories)
    try:
        lessons = _outcome_recall(query, limit=2)
        _inject_outcome_lessons(lessons, ctx)
    except Exception:
        _log.debug("outcome recall skipped", exc_info=True)

    # Tier 6: typed memories (code_fact, routing_lesson, reference_pattern)
    try:
        typed = _typed_memory_recall(limit=3)
        _inject_typed_memories(typed, ctx)
    except Exception:
        _log.debug("typed memory recall skipped", exc_info=True)

    ctx.recalled_memory_ids = recalled_ids
    return ctx


def _typed_memory_recall(limit: int = 3) -> list:
    """Tier 6: query typed memories (code_fact, routing_lesson, reference_pattern).

    These are the deeper, structured memories promoted from patterns —
    previously queried independently by routing_engine in coding scenarios.
    Now unified into the single memory recall entry point.
    """
    typed: list = []
    try:
        from session_memory.store_promote import query_by_type

        for mt in ("code_fact", "routing_lesson", "reference_pattern"):
            for mem in query_by_type(mt, limit=limit):
                typed.append((mt, mem.summary))
    except ImportError:
        _log.debug("store_promote not available")
    except Exception:
        _log.debug("typed memory recall failed", exc_info=True)
    return typed


def _inject_typed_memories(typed: list, ctx: RequestContext) -> None:
    """Inject typed memories as 'Past coding decisions' system prompt."""
    if not typed:
        return
    lines = ["Past coding decisions:"]
    for mt, summary in typed:
        lines.append(f"[{mt}] {summary}")
    text = "\n".join(lines)[:800]
    if ctx.system_prompt:
        ctx.system_prompt += "\n\n" + text
    else:
        ctx.system_prompt = text


def save_request_memory(
    headers: dict, messages: list[dict], response_summary: str = ""
) -> None:
    """Save a request/response pair as a memory entry with embedding."""
    if os.environ.get("LIMA_SESSION_MEMORY", "0") != "1":
        return

    session_id = _session_id_from_headers(headers)

    query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            query = msg["content"]
            break

    if not query or len(query) < 5:
        return

    summary = query[:100]
    if response_summary:
        summary += f"  {response_summary[:100]}"

    from session_memory.embeddings import save_memory_with_embedding

    save_memory_with_embedding(
        session_id=session_id, role="exchange", summary=summary,
    )
