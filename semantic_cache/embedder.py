"""Embedding backends for the semantic cache."""

from __future__ import annotations

import asyncio
import math
import random
import threading
from collections import OrderedDict
from typing import Protocol, runtime_checkable

from code_context.embedding_client import get_embeddings, get_embeddings_async
from semantic_cache.config import embedding_cache_size


@runtime_checkable
class Embedder(Protocol):
    """Protocol for query embedders."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class _EmbeddingLRUCache:
    """Thread-safe LRU cache for query -> embedding vectors."""

    def __init__(self, maxsize: int) -> None:
        self.maxsize = max(0, maxsize)
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(text: str, dimensions: int, key_hash: str) -> str:
        return f"{dimensions}:{key_hash}:{text}"

    def get(self, text: str, dimensions: int, key_hash: str) -> list[float] | None:
        if self.maxsize == 0:
            return None
        key = self._key(text, dimensions, key_hash)
        with self._lock:
            vector = self._cache.get(key)
            if vector is not None:
                self._cache.move_to_end(key)
            return vector

    def set(self, text: str, dimensions: int, key_hash: str, vector: list[float]) -> None:
        if self.maxsize == 0:
            return
        key = self._key(text, dimensions, key_hash)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                self._cache[key] = vector
                if len(self._cache) > self.maxsize:
                    self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class JinaEmbedder:
    """Jina AI embedding backend (network required) with per-vector LRU cache."""

    def __init__(self, *, dimensions: int = 256, api_key: str = ""):
        self.dimensions = dimensions
        self.api_key = api_key
        self._cache = _EmbeddingLRUCache(maxsize=embedding_cache_size())
        self._async_lock = asyncio.Lock()

    def _key_hash(self) -> str:
        # A short stable identifier for the API key so key rotation invalidates cache.
        return str(hash(self.api_key or "no-key"))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        key_hash = self._key_hash()
        result: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str]] = []

        for idx, text in enumerate(texts):
            cached = self._cache.get(text, self.dimensions, key_hash)
            if cached is not None:
                result[idx] = cached
            else:
                missing.append((idx, text))

        if not missing:
            return [v for v in result if v is not None]

        response = get_embeddings(
            [text for _, text in missing],
            dimensions=self.dimensions,
            api_key=self.api_key,
        )
        if not response:
            # Preserve existing contract: network failure returns empty list.
            return []

        if len(response) != len(missing):
            # Unexpected shape; don't cache mismatched results.
            return []

        for (idx, text), vector in zip(missing, response, strict=True):
            self._cache.set(text, self.dimensions, key_hash, vector)
            result[idx] = vector

        return [v for v in result if v is not None]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Async variant that shares the same LRU cache as embed()."""
        if not texts:
            return []

        key_hash = self._key_hash()
        result: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str]] = []

        for idx, text in enumerate(texts):
            cached = self._cache.get(text, self.dimensions, key_hash)
            if cached is not None:
                result[idx] = cached
            else:
                missing.append((idx, text))

        if not missing:
            return [v for v in result if v is not None]

        async with self._async_lock:
            # Re-check cache after acquiring lock; another coroutine may have filled it.
            still_missing: list[tuple[int, str]] = []
            for idx, text in missing:
                cached = self._cache.get(text, self.dimensions, key_hash)
                if cached is not None:
                    result[idx] = cached
                else:
                    still_missing.append((idx, text))

            if not still_missing:
                return [v for v in result if v is not None]

            response = await get_embeddings_async(
                [text for _, text in still_missing],
                dimensions=self.dimensions,
                api_key=self.api_key,
            )
            if not response or len(response) != len(still_missing):
                return []

            for (idx, text), vector in zip(still_missing, response, strict=True):
                self._cache.set(text, self.dimensions, key_hash, vector)
                result[idx] = vector

        return [v for v in result if v is not None]


class FakeEmbedder:
    """Deterministic local embedder for tests and offline fallback.

    Not semantically meaningful, but produces stable vectors so cosine similarity
    is 1.0 for identical strings and roughly distributed otherwise.
    """

    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        rng = random.Random(text)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self.dimensions)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
