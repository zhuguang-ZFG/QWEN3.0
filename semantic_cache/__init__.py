"""Semantic cache for LLM chat responses (P4-5 baseline)."""

from .cache import SemanticCache
from .embedder import FakeEmbedder, JinaEmbedder

__all__ = [
    "FakeEmbedder",
    "JinaEmbedder",
    "SemanticCache",
]
