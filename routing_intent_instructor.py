"""Optional Instructor-based intent fallback for low-confidence rule classification."""

from __future__ import annotations

import hashlib
import time
from functools import lru_cache
from typing import Any

from config import env as _env
from models.structured_outputs import IntentResult, instructor_client
from observability.events import instructor_intent_event, instructor_intent_latency_event
from observability.metrics import record as _record_metric

_INSTRUCTOR_INTENT_PROMPT = (
    "You are an intent classifier for an AI assistant. Analyze the user query and "
    "output a JSON object matching the required schema. Fields:\n"
    "- intent: one of [chat, code_generation, debugging, explanation, hardware, "
    "image_gen, device_draw, device_write, device_control, thinking, trivial, "
    "architecture, tool_task, grbl_config, cnc_trouble, embedded_dev, general_cnc, "
    "complex_theory]\n"
    "- confidence: float 0.0-1.0\n"
    "- complexity: float 0.0-1.0\n"
    "- needs_code: boolean\n"
    "- domain_keywords: list of relevant keywords\n"
    "- cnc_subdomain: 'grbl' or 'general'\n"
    "- entities: dict of detected entities\n"
    "Be concise and return only valid JSON."
)

# AUDIT-8-P1: cache low-confidence instructor intent results to avoid repeating
# the same network LLM call for identical queries. Cache key includes provider
# and model so key/endpoint rotations invalidate stale entries automatically.
_INSTRUCTOR_CACHE_SIZE = 256


def _cache_key(query: str, system_prompt: str, ide: str, provider: str, model: str) -> str:
    return hashlib.sha256(f"{provider}:{model}:{ide}:{system_prompt}:{query}".encode("utf-8")).hexdigest()


def _build_messages(query: str, system_prompt: str, ide: str) -> list[dict]:
    return [
        {"role": "system", "content": _INSTRUCTOR_INTENT_PROMPT},
        {"role": "user", "content": f"Query: {query}\nIDE: {ide}\nSystem context: {system_prompt}"},
    ]


@lru_cache(maxsize=_INSTRUCTOR_CACHE_SIZE)
def _cached_instructor_call(
    key: str,
    query: str,
    system_prompt: str,
    ide: str,
    provider: str,
    model: str,
) -> IntentResult | None:
    """Synchronously call Instructor with LRU memoization."""
    result = instructor_client.create_structured_completion(
        messages=_build_messages(query, system_prompt, ide),
        response_model=IntentResult,
        provider=provider,
        model=model,
        max_retries=_env.instructor_intent_max_retries(),
        timeout=_env.instructor_intent_timeout(),
    )
    return result


def maybe_instructor_intent(
    query: str,
    system_prompt: str = "",
    ide: str = "unknown",
) -> dict[str, Any] | None:
    """Call Instructor to classify intent when rule confidence is low.

    Returns None if disabled, if dependencies/keys are missing, or if the call
    fails. On failure a warning is logged and metrics are recorded.
    Results are cached per (query, system_prompt, ide, provider, model).
    """
    if not _env.instructor_intent_enabled():
        return None

    provider = _env.instructor_intent_provider()
    model = _env.instructor_intent_model()
    start = time.perf_counter()

    key = _cache_key(query, system_prompt, ide, provider, model)
    result = _cached_instructor_call(key, query, system_prompt, ide, provider, model)

    latency_ms = (time.perf_counter() - start) * 1000.0
    if result is None:
        _record_metric(instructor_intent_event(provider, model, False, reason="no_result"))
        return None

    _record_metric(instructor_intent_event(provider, model, True))
    _record_metric(instructor_intent_latency_event(provider, model, latency_ms))
    dumped = result.model_dump()
    dumped["instructor_used"] = True
    return dumped


async def amaybe_instructor_intent(
    query: str,
    system_prompt: str = "",
    ide: str = "unknown",
) -> dict[str, Any] | None:
    """Async variant of maybe_instructor_intent for non-blocking callers.

    This path does not share the sync LRU cache; it is provided for future
    async route handlers. The sync production path remains maybe_instructor_intent.
    """
    if not _env.instructor_intent_enabled():
        return None

    provider = _env.instructor_intent_provider()
    model = _env.instructor_intent_model()
    start = time.perf_counter()

    result = await instructor_client.create_structured_completion_async(
        messages=_build_messages(query, system_prompt, ide),
        response_model=IntentResult,
        provider=provider,
        model=model,
        max_retries=_env.instructor_intent_max_retries(),
        timeout=_env.instructor_intent_timeout(),
    )

    latency_ms = (time.perf_counter() - start) * 1000.0
    if result is None:
        _record_metric(instructor_intent_event(provider, model, False, reason="no_result"))
        return None

    _record_metric(instructor_intent_event(provider, model, True))
    _record_metric(instructor_intent_latency_event(provider, model, latency_ms))
    dumped = result.model_dump()
    dumped["instructor_used"] = True
    return dumped
