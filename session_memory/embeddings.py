"""Memory embedding bridge — connects Jina AI embeddings to session_memory.

Provides save_memory_with_embedding() which generates an embedding vector
for the summary text before saving. Falls back gracefully (saves without
embedding) if the embedding service is unavailable.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)

_EMBED_ENABLED = os.environ.get("LIMA_MEMORY_EMBED", "1").strip().lower() in {
    "1", "true", "yes",
}


def _generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a text. Returns empty on failure."""
    if not _EMBED_ENABLED:
        return []
    if not text or not text.strip():
        return []
    if not os.environ.get("JINA_API_KEY", ""):
        return []

    try:
        from code_context.embedding_client import get_embeddings

        results = get_embeddings([text[:2000]], dimensions=128)
        if results and results[0]:
            return results[0]
    except ImportError:
        _log.debug("code_context.embedding_client not installed")
    except Exception:
        _log.debug("embedding generation failed", exc_info=True)

    return []


def save_memory_with_embedding(
    session_id: str,
    role: str,
    summary: str,
    detail: str = "",
    memory_type: str = "exchange",
) -> int:
    """Save a memory entry with embedding + ChromaDB sync."""
    from session_memory.store_crud import save_memory

    embedding = _generate_embedding(summary)
    entry_id = save_memory(
        session_id=session_id,
        role=role,
        summary=summary,
        detail=detail,
        embedding=embedding if embedding else None,
        memory_type=memory_type,
    )

    # Sync to ChromaDB for local semantic search (fire-and-forget)
    if entry_id:
        try:
            from session_memory.chroma_store import add_memory
            add_memory(entry_id, session_id, summary, memory_type)
        except Exception:
            pass  # ChromaDB sync is best-effort

    return entry_id
