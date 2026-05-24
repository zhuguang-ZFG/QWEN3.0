"""Session memory processor for context_pipeline integration."""

import hashlib
import os

from context_pipeline import RequestContext
from session_memory.store import (
    get_recent_memories,
    save_memory,
    search_memories_keyword,
)


def _session_id_from_headers(headers: dict) -> str:
    """Derive session ID from request headers (IP + User-Agent hash)."""
    ip = headers.get("x-forwarded-for", headers.get("x-real-ip", "unknown"))
    ua = headers.get("user-agent", "")
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def session_memory_processor(ctx: RequestContext) -> RequestContext:
    """Pipeline processor: inject relevant session memories into context.

    Returns ctx with system_prompt augmented and recalled_memory_ids set
    on the context so callers can attach source citations to admin traces.
    """
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

    memories = search_memories_keyword(session_id, query[:50], limit=3)
    if not memories:
        memories = get_recent_memories(session_id, limit=2)

    recalled_ids: list[int] = []
    if memories:
        lines = ["[会话记忆]"]
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


def save_request_memory(
    headers: dict, messages: list[dict], response_summary: str = ""
) -> None:
    """Save a request/response pair as a memory entry (called after response)."""
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
        summary += f" → {response_summary[:100]}"

    save_memory(session_id=session_id, role="exchange", summary=summary)
