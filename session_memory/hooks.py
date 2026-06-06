"""Session memory lifecycle hooks — automatic memory capture at key events.

Based on claude-mem lifecycle hook pattern:
- on_request_start: Load relevant memories for context injection
- on_response_complete: Save interaction summary
- on_error: Record failure as a routing lesson
- on_session_end: Trigger compaction if needed
"""

import os

from session_memory.processor import _session_id_from_headers, save_request_memory


def on_request_start(headers: dict, messages: list[dict]) -> str:
    """Hook: fired at request start. Returns session_id."""
    if os.environ.get("LIMA_SESSION_MEMORY", "0") != "1":
        return ""
    return _session_id_from_headers(headers)


def on_response_complete(
    headers: dict,
    messages: list[dict],
    response_text: str,
    backend: str = "",
) -> None:
    """Hook: fired after successful response. Saves interaction memory."""
    if os.environ.get("LIMA_SESSION_MEMORY", "0") != "1":
        return

    summary = response_text[:80] if response_text else ""
    if backend:
        summary = f"[{backend}] {summary}"
    save_request_memory(headers, messages, response_summary=summary)


def on_error(
    headers: dict,
    messages: list[dict],
    backend: str,
    error: str,
) -> None:
    """Hook: fired on backend error. Records failure as lesson."""
    if os.environ.get("LIMA_SESSION_MEMORY", "0") != "1":
        return

    from user_identity.lessons import add_lesson

    session_id = _session_id_from_headers(headers)
    query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            query = msg["content"][:50]
            break

    lesson_content = f"{backend} failed: {error[:80]}"
    if query:
        lesson_content += f" (query: {query})"

    add_lesson(session_id, domain="routing", content=lesson_content)
