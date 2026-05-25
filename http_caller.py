"""
LiMa HTTP Caller — unified backend transport layer.

Extracted modules (CQ-014 slice 8):
  http_errors.py           BackendError + status helpers
  http_request_builder.py  client factory, headers, body, key pool
  http_response.py         answer/usage/SSE parsing
  http_stream.py             sync/async SSE streaming
"""

from __future__ import annotations

import os
import sys
import time

import health_tracker
import httpx
import key_pool
from response_cleaner import clean_response, _is_backend_error

from backends import BACKENDS, GFW_BACKENDS
from http_errors import BackendError, _emit_backend_error, _extract_code, _extract_retry_after
from http_request_builder import (
    GFW_PROXY_URL,
    GFW_USER_AGENT,
    _build_async_client,
    _build_body,
    _build_client,
    _build_headers,
    _has_key,
    _key_pool_provider,
    _report_key_result,
    _select_key,
)
from http_response import _extract_answer, _extract_usage, _parse_sse_chunk
from http_stream import call_api_stream, call_api_stream_async

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"


def call_api(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
) -> str:
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)

    if health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down", status_code=503)

    try:
        from context_pipeline.artifact import create_handle, should_use_handle

        for index, msg in enumerate(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and should_use_handle(content):
                    messages[index] = {**msg, "content": create_handle(content)}
    except ImportError:
        pass

    started = time.time()
    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide)
    timeout = cfg.get("timeout", 60)

    try:
        with _build_client(backend, timeout) as client:
            resp = client.post(cfg["url"], content=body, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

        answer = _extract_answer(payload, cfg["fmt"])

        if _is_backend_error(answer):
            health_tracker.record_failure(
                backend, error_code=429, error_text=answer
            )
            raise BackendError(
                f"{backend} returned error response: {answer[:60]}",
                status_code=429,
            )

        latency_ms = int((time.time() - started) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        health_tracker.record_response_quality(
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

        try:
            from observability.metrics import record as obs_record
            from observability.events import backend_call_event

            obs_record(
                backend_call_event("", backend, "", latency_ms=latency_ms)
            )
        except ImportError:
            pass

        return cleaned

    except BackendError as exc:
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        _emit_backend_error(backend, exc.status_code, str(exc))
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        _emit_backend_error(backend, error_code, str(exc))
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        _emit_backend_error(backend, error_code, str(exc))
        if DEBUG:
            print(f"[HTTP] {backend} error: {exc}", file=sys.stderr)
        raise BackendError(str(exc), status_code=error_code) from exc


def call_raw(backend: str, payload: bytes) -> dict:
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable", status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable", status_code=404)
    started = time.time()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {selected_key}",
    }
    try:
        with _build_client(backend, cfg.get("timeout", 30)) as client:
            resp = client.post(cfg["url"], content=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.time() - started) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        return data
    except BackendError as exc:
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc


async def call_api_async(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
) -> str:
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)

    if health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooled down", status_code=503)

    started = time.time()
    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide)
    timeout = cfg.get("timeout", 60)

    try:
        async with _build_async_client(backend, timeout) as client:
            resp = await client.post(cfg["url"], content=body, headers=headers)
            resp.raise_for_status()
            payload = resp.json()

        answer = _extract_answer(payload, cfg["fmt"])

        if _is_backend_error(answer):
            health_tracker.record_failure(
                backend, error_code=429, error_text=answer
            )
            raise BackendError(
                f"{backend} returned error response: {answer[:60]}",
                status_code=429,
            )

        latency_ms = int((time.time() - started) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        health_tracker.record_response_quality(
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

    except BackendError as exc:
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        if DEBUG:
            print(f"[HTTP] {backend} async error: {exc}", file=sys.stderr)
        raise BackendError(str(exc), status_code=error_code) from exc


async def call_raw_async(backend: str, payload: bytes) -> dict:
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable", status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable", status_code=404)
    started = time.time()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {selected_key}",
    }
    try:
        async with _build_async_client(backend, cfg.get("timeout", 30)) as client:
            resp = await client.post(cfg["url"], content=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.time() - started) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        return data
    except BackendError as exc:
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        _report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc


def probe(backend: str) -> bool:
    try:
        call_api(
            backend,
            [{"role": "user", "content": "hi"}],
            max_tokens=1,
            system_prompt="Reply with one word.",
        )
        return True
    except BackendError:
        return False
