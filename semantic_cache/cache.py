"""High-level semantic cache API."""

from __future__ import annotations

import hashlib
import logging
import math
from typing import TYPE_CHECKING

from semantic_cache.config import (
    cache_enabled,
    default_ttl_seconds,
    embedding_dimensions,
    similarity_threshold,
)
from semantic_cache.embedder import FakeEmbedder, JinaEmbedder
from semantic_cache.store import SemanticCacheStore

if TYPE_CHECKING:
    from semantic_cache.embedder import Embedder

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


class SemanticCache:
    """Embedding-based response cache with pluggable embedder."""

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        store: SemanticCacheStore | None = None,
        threshold: float | None = None,
        ttl_seconds: int | None = None,
    ):
        self.embedder = embedder or self._default_embedder()
        self.store = store or SemanticCacheStore()
        self.threshold = threshold if threshold is not None else similarity_threshold()
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else default_ttl_seconds()

    @staticmethod
    def _default_embedder() -> Embedder:
        # Prefer Jina when a key is configured; otherwise fall back to the
        # deterministic fake embedder so the cache works offline/tests.
        from semantic_cache.config import jina_api_key

        if jina_api_key():
            return JinaEmbedder(dimensions=embedding_dimensions())
        logger.warning("Jina API key not configured; semantic cache uses offline fake embedder")
        return FakeEmbedder(dimensions=embedding_dimensions())

    def lookup(
        self,
        query: str,
        *,
        threshold: float | None = None,
        ttl_seconds: int | None = None,
    ) -> str | None:
        """Return a cached response if a sufficiently similar query exists."""
        if not query or not query.strip():
            return None

        threshold = threshold if threshold is not None else self.threshold
        ttl_seconds = ttl_seconds if ttl_seconds is not None else self.ttl_seconds

        query_embedding = self._embed_single(query)
        min_created_at = __import__("time").time() - ttl_seconds
        candidates = self.store.get_candidates(min_created_at)

        best: tuple[float, int, str] | None = None
        for entry in candidates:
            sim = _cosine_similarity(query_embedding, entry.embedding)
            if sim >= threshold and (best is None or sim > best[0]):
                best = (sim, entry.id, entry.response)

        if best is None:
            return None

        self.store.bump_hit_count(best[1])
        logger.info("semantic cache hit (sim=%.3f)", best[0])
        return best[2]

    def store_response(self, query: str, response: str) -> None:
        """Cache a query/response pair."""
        if not query or not response:
            return
        embedding = self._embed_single(query)
        self.store.upsert(_query_hash(query), query, embedding, response)

    def _embed_single(self, query: str) -> list[float]:
        embeddings = self.embedder.embed([query])
        if not embeddings:
            raise RuntimeError("embedder returned no vectors")
        return embeddings[0]

    def clear(self) -> None:
        """Remove all cached entries."""
        self.store.clear()


def get_cache() -> SemanticCache | None:
    """Return a configured cache if enabled, otherwise None."""
    if not cache_enabled():
        return None
    return SemanticCache()
