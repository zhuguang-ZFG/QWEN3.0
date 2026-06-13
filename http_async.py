"""Async HTTP API calls extracted from http_caller (CQ-014 slice 10)."""

from __future__ import annotations

import time

from response_cleaner import clean_response, _is_backend_error

from backends_registry import BACKENDS
from http_errors import BackendError
from http_response import _extract_answer, _extract_usage
from http_sync import _handle_call_error


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
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, tools=tools)
    timeout = cfg.get("timeout", 60)

    try:
        async with hc._build_async_client(backend, timeout) as client:
            resp = await client.post(cfg["url"], content=body, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

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
        try:
            import budget_manager

            budget_manager.record_token_usage(
                backend, prompt_tokens, completion_tokens
            )
        except ImportError:
            pass
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
