"""Session memory processor for context_pipeline integration.

Uses keyword search (SQL LIKE) as primary path, semantic search (cosine
similarity on Jina AI embeddings) as fallback when keyword misses.
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
    """Derive session ID from request headers (IP + User-Agent hash)."""
    ip = headers.get("x-forwarded-for", headers.get("x-real-ip", "unknown"))
    ua = headers.get("user-agent", "")
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _semantic_fallback(session_id: str, query: str, limit: int = 3) -> list:
    """Try semantic search when keyword search returns nothing."""
    try:
        from code_context.embedding_client import get_embeddings

        emb = get_embeddings([query[:2000]], dimensions=128)
        if not emb or not emb[0]:
            return []
        from session_memory.store import search_memories_semantic

        return search_memories_semantic(session_id, emb[0], limit=limit)
    except ImportError:
        _log.warning("semantic search not available")
    except Exception:
        _log.warning("semantic search failed", exc_info=True)
    return []


def _cross_session_fallback(query: str, limit: int = 2) -> list:
    """Search global (cross-session) memories when per-session misses."""
    try:
        return search_memories_keyword("_global", query[:50], limit=limit)
    except Exception:
        _log.warning("cross-session memory search failed", exc_info=True)
        return []


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

    # Tier 2: semantic search (Jina AI embeddings)
    if not memories:
        memories = _semantic_fallback(session_id, query, limit=3)

    # Tier 3: cross-session global search
    if not memories:
        cross = _cross_session_fallback(query, limit=2)
        memories = cross

    # Tier 4: recent memories (always available)
    if not memories:
        memories = get_recent_memories(session_id, limit=2)

    recalled_ids: list[int] = []
    if memories:
        lines = ["[session memory]"]
        for m in memories:
            recalled_ids.append(m.id)
            lines.append(f"- [{m.role}] {m.summary}")
        memory_text = "\n".join(lines)[:600]

        if ctx.system_prompt:
            ctx.system_prompt += "\n\n" + memory_text
        else:
            ctx.system_prompt = memory_text

    ctx.recalled_memory_ids = recalled_ids
    return ctx


def save_request_memory(headers: dict, messages: list[dict], response_summary: str = "") -> None:
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
        session_id=session_id,
        role="exchange",
        summary=summary,
    )
