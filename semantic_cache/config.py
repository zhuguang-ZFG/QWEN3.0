"""Semantic cache configuration."""

from __future__ import annotations

import os

from config.settings import EMBEDDING


def cache_enabled() -> bool:
    """Whether the semantic cache is enabled."""
    return os.environ.get("LIMA_SEMANTIC_CACHE_ENABLED", "0").lower() in {"1", "true", "on"}


def cache_db_path() -> str:
    """SQLite path for the semantic cache."""
    default = os.path.join(os.environ.get("LIMA_DATA_DIR", "data"), "semantic_cache.db")
    return os.environ.get("LIMA_SEMANTIC_CACHE_DB", default)


def similarity_threshold() -> float:
    """Default cosine-similarity threshold for cache hits."""
    try:
        return float(os.environ.get("LIMA_SEMANTIC_CACHE_THRESHOLD", "0.92"))
    except ValueError:
        return 0.92


def default_ttl_seconds() -> int:
    """Default cache entry TTL in seconds."""
    try:
        return int(os.environ.get("LIMA_SEMANTIC_CACHE_TTL", "3600"))
    except ValueError:
        return 3600


def embedding_dimensions() -> int:
    """Embedding dimensions (must match the embedder)."""
    try:
        return int(os.environ.get("LIMA_SEMANTIC_CACHE_DIMENSIONS", "256"))
    except ValueError:
        return 256


def jina_api_key() -> str:
    """Jina API key for the default embedder."""
    return EMBEDDING.jina_api_key
