"""routes/request_context_preflight.py compatibility wrapper.

Legacy index-based preflight helpers remain for unit tests. Production request
paths should use context_pipeline.retrieval_injection.inject_retrieval_context().
"""

import os

from code_context.index_store import InMemoryCodeIndex


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def enhance_messages(
    messages: list[dict],
    *,
    index: InMemoryCodeIndex,
    query_embedding: list[float] | None = None,
    max_chars: int = 1200,
) -> list[dict]:
    """Lab helper: inject context from an in-memory code index."""
    query = _last_user_text(messages)
    if not query:
        return messages

    if query_embedding:
        matches = index.semantic_search(query_embedding, limit=3)
    else:
        matches = index.search(query, limit=3)

    if not matches:
        return messages

    lines = ["[LiMa code context: relevant local files]"]
    for record in matches:
        symbols = ", ".join(
            f"{symbol.name}:{symbol.kind}:{symbol.line}"
            for symbol in record.symbols[:8]
        )
        lines.append(f"- {record.path} | {symbols}")

    context = "\n".join(lines)[:max_chars]
    return [{"role": "system", "content": context}] + list(messages)


def maybe_enhance_messages(messages: list[dict], *, index: InMemoryCodeIndex | None) -> list[dict]:
    """Preflight hook that delegates to the unified retrieval injection path."""
    if os.environ.get("LIMA_CONTEXT_PREFLIGHT", "0") != "1":
        return messages

    from context_pipeline.retrieval_injection import inject_retrieval_context

    enhanced, _ = inject_retrieval_context(messages)
    return enhanced
