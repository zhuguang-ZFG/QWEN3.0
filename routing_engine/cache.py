"""Semantic cache integration helpers for routing_engine."""

from __future__ import annotations

import logging
import time

from observability.events import semantic_cache_event
from observability.metrics import record as _record_metric
from .trace import trace_span
from semantic_cache.cache import get_cache

logger = logging.getLogger(__name__)


def lookup_cached_response(query: str, request_type: str) -> str | None:
    """Return cached response when semantic cache is enabled and query is cacheable."""
    if request_type != "chat" or not query or not query.strip():
        _record_metric(semantic_cache_event("skip"))
        return None
    cache = get_cache()
    if cache is None:
        _record_metric(semantic_cache_event("skip"))
        return None

    start = time.perf_counter()
    try:
        response = cache.lookup(query)
        latency_ms = (time.perf_counter() - start) * 1000.0
        if response:
            _record_metric(semantic_cache_event("hit", latency_ms=latency_ms))
        else:
            _record_metric(semantic_cache_event("miss", latency_ms=latency_ms))
        return response
    except Exception as exc:  # pragma: no cover - embedder/network failures
        latency_ms = (time.perf_counter() - start) * 1000.0
        logger.warning("semantic cache lookup failed: %s", exc)
        _record_metric(semantic_cache_event("error", latency_ms=latency_ms))
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
        _record_metric(semantic_cache_event("store"))
    except Exception as exc:  # pragma: no cover - embedder/network failures
        logger.warning("semantic cache store failed: %s", exc)
        _record_metric(semantic_cache_event("error"))


def traced_lookup_cached_response(
    query: str,
    request_type: str,
    cache_enabled: bool,
) -> tuple[str | None, str, int]:
    """语义缓存查询并生成 trace span。

    返回 (cached_answer, cache_status, cache_lookup_ms)。
    """
    cache_status = "skip"
    cached_answer: str | None = None
    cache_lookup_ms = 0
    cache_present = get_cache() is not None

    with trace_span("semantic_cache") as span:
        t0 = time.perf_counter()
        try:
            if cache_enabled and cache_present and request_type == "chat":
                cached_answer = lookup_cached_response(query, request_type)
                cache_status = "hit" if cached_answer is not None else "miss"
            else:
                cache_status = "skip"
        except Exception as exc:
            cache_status = "error"
            logger.warning("semantic cache lookup failed in route: %s", exc)
        finally:
            cache_lookup_ms = int((time.perf_counter() - t0) * 1000)
            if span is not None:
                span.metadata["cache_enabled"] = cache_enabled and cache_present
                span.metadata["cache_status"] = cache_status
                span.metadata["cache_lookup_ms"] = cache_lookup_ms

    return cached_answer, cache_status, cache_lookup_ms
