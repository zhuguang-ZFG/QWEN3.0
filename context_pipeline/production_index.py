"""Production in-memory retrieval index for routing corpus."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from context_pipeline.retrieval_corpus import resolve_production_corpus_paths
from local_retrieval.index import InMemoryTokenIndex

if TYPE_CHECKING:
    from context_pipeline.graph_retrieval import RetrievalResult

_index: InMemoryTokenIndex | None = None


def get_production_index(*, refresh: bool = False) -> InMemoryTokenIndex | None:
    """Build or return singleton token index over production corpus files."""
    global _index
    if _index is not None and not refresh:
        return _index

    paths = resolve_production_corpus_paths()
    if not paths:
        return None

    index = InMemoryTokenIndex(index_id="lima-production-routing", max_chars=800)
    if index.add_documents(paths) <= 0:
        return None

    _index = index
    return _index


def reset_production_index() -> None:
    """Clear cached index (for tests)."""
    global _index
    _index = None


def search_production_corpus(query: str, top_k: int = 8) -> list["RetrievalResult"]:
    """Search production corpus and return graph_retrieval-compatible results."""
    from context_pipeline.graph_retrieval import RetrievalResult

    index = get_production_index()
    if index is None or not query.strip():
        return []

    hits = index.search(query.strip(), top_k=top_k)
    results: list[RetrievalResult] = []
    for hit in hits:
        results.append(RetrievalResult(
            path=os.path.basename(hit.document_path),
            score=max(hit.score, 0.1),
            source="vector",
            snippet=hit.snippet[:200] if hit.snippet else "",
        ))
    return results
