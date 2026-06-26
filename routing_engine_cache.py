"""Semantic cache integration helpers for routing_engine."""

from __future__ import annotations

import logging

from semantic_cache.cache import SemanticCache, get_cache

logger = logging.getLogger(__name__)


def lookup_cached_response(query: str, request_type: str) -> str | None:
    """Return cached response when semantic cache is enabled and query is cacheable."""
    if request_type != "chat" or not query or not query.strip():
        return None
    cache = get_cache()
    if cache is None:
        return None
    try:
        return cache.lookup(query)
    except Exception as exc:  # pragma: no cover - embedder/network failures
        logger.warning("semantic cache lookup failed: %s", exc)
        return None


def store_cached_response(query: str, answer: str, request_type: str) -> None:
    """Store a chat response in the semantic cache."""
    if request_type != "chat" or not query or not answer:
        return
    cache = get_cache()
    if cache is None:
        return
    try:
        cache.store_response(query, answer)
    except Exception as exc:  # pragma: no cover - embedder/network failures
        logger.warning("semantic cache store failed: %s", exc)
