"""Embedding backends for the semantic cache."""

from __future__ import annotations

import math
import random
from typing import Protocol, runtime_checkable

from code_context.embedding_client import get_embeddings


@runtime_checkable
class Embedder(Protocol):
    """Protocol for query embedders."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class JinaEmbedder:
    """Jina AI embedding backend (network required)."""

    def __init__(self, *, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return get_embeddings(texts, dimensions=self.dimensions)


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
