"""Compatibility retrieval facade for the code_context package.

The first Potpie-inspired plan named this boundary `code_context.retriever`.
The concrete index implementation lives in `code_context.index_store`; this
module keeps the planned import path stable while preserving the small local
MVP shape.
"""
from __future__ import annotations

from .index_store import FileRecord, InMemoryCodeIndex


def retrieve_relevant_files(
    index: InMemoryCodeIndex,
    query: str,
    *,
    limit: int = 5,
    query_embedding: list[float] | None = None,
) -> list[FileRecord]:
    """Return relevant indexed files by semantic embedding or keyword query."""
    if query_embedding:
        return index.semantic_search(query_embedding, limit=limit)
    return index.search(query, limit=limit)
