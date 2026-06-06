"""Async HTTP API calls extracted from http_caller (CQ-014 slice 10)."""

from __future__ import annotations

import asyncio
import logging
import time

from backends import BACKENDS
from backends_constants import KEY_POOL_PREFIXES
from http_errors import BackendError
from http_response import _extract_answer, _extract_usage
from http_sync import _handle_call_error
from response_cleaner import _is_backend_error, clean_response

_log = logging.getLogger(__name__)

# ── Usage tracking (asyncio single-threaded, no lock needed) ──────────────
_last_usage: dict[str, dict] = {}
"""Async per-backend last usage cache.
Safe without lock: asyncio is single-threaded per event loop.
"""

# ── Provider-level concurrency limiter ─────────────────────────────────────
# Prevents multiple backends sharing the same API key from flooding
# the provider and triggering rate-limit cascades (e.g. NVIDIA NIM 40 RPM).
# Each provider gets an asyncio.Semaphore — calls wait in the event loop
# instead of failing with 429.
_PROVIDER_MAX_CONCURRENT: dict[str, int] = {
    "nvidia": 3,
}
_provider_semaphores: dict[str, asyncio.Semaphore] = {}


def _resolve_provider(backend: str) -> str | None:
    """Map backend name to its key-pool provider (e.g. 'nvidia_qwen_coder' → 'nvidia')."""
    for prefix, provider in KEY_POOL_PREFIXES.items():
        if backend.startswith(prefix):
            return provider
    return None


def _get_provider_semaphore(backend: str) -> asyncio.Semaphore | None:
    """Return an asyncio.Semaphore for the backend's provider, if rate-limited."""
    provider = _resolve_provider(backend)
    if not provider or provider not in _PROVIDER_MAX_CONCURRENT:
        return None
    if provider not in _provider_semaphores:
        _provider_semaphores[provider] = asyncio.Semaphore(_PROVIDER_MAX_CONCURRENT[provider])
        _log.info("provider_semaphore created: %s (max_concurrent=%d)", provider, _PROVIDER_MAX_CONCURRENT[provider])
    return _provider_semaphores[provider]


def get_last_usage(backend: str) -> dict | None:
    """Return the last recorded usage dict for a backend, or None."""
    return _last_usage.get(backend)


def _caller():
    import http_caller

    return http_caller


async def call_api_async(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
    tools: list[dict] | None = None,
    reasoning_effort: str | None = None,
) -> str:
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if hc.health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down", status_code=503)

    started = time.time()
    headers = hc._build_headers(cfg, key=selected_key)
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, tools=tools,
                          reasoning_effort=reasoning_effort, backend_name=backend)
    timeout = cfg.get("timeout", 60)

    # Provider-level concurrency gate: acquire semaphore before HTTP call.
    # This prevents multiple backends sharing one API key from flooding the
    # provider (e.g. NVIDIA NIM free tier 40 RPM).  Calls wait in the event
    # loop instead of failing with 429, and the key pool's 429 cooldown
    # provides additional backpressure.
    sem = _get_provider_semaphore(backend)

    async def _do_call():
        client = hc._get_async_client(backend, timeout)
        resp = await client.post(cfg["url"], content=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    try:
        if sem:
            async with sem:
                payload = await _do_call()
        else:
            payload = await _do_call()

        answer = _extract_answer(payload, cfg["fmt"])
        if _is_backend_error(answer):
            hc.health_tracker.record_failure(
                backend, error_code=429, error_text=answer
            )
            raise BackendError(
                f"{backend} returned error response: {answer[:60]}",
                status_code=429,
            )

        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        hc.health_tracker.record_response_quality(
            backend, len(cleaned) if cleaned else 0
        )
        prompt_tokens, completion_tokens = _extract_usage(payload, cfg["fmt"])
        _last_usage[backend] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        try:
            import budget_manager

            budget_manager.record_token_usage(
                backend, prompt_tokens, completion_tokens
            )
        except ImportError:
            _log.debug("http_async: optional module not available", exc_info=True)
        return cleaned
    except Exception as exc:
        _handle_call_error(backend, key_provider, selected_key, exc, emit_obs=False)


async def call_raw_async(backend: str, payload: bytes) -> dict:
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable", status_code=404)
    started = time.time()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {selected_key}",
    }
    try:
        async with hc._build_async_client(backend, cfg.get("timeout", 30)) as client:
            resp = await client.post(cfg["url"], content=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        return data
    except Exception as exc:
        _handle_call_error(backend, key_provider, selected_key, exc, emit_obs=False)
