"""Sync and async SSE streaming entry points for http_caller (CQ-014 slice 8)."""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Generator

import httpx
from backends_registry import BACKENDS
from http_errors import BackendError
from http_stream_core import (
    _record_stream_error,
    _record_stream_success,
    _stream_parse_lines,
    _stream_parse_lines_async,
)
from response_cleaner import StreamIdentitySanitizer  # noqa: F401  re-export imported by tests
from http_sync import _enforce_https_scheme


def _caller():
    """Resolve http_caller at runtime so tests can patch _build_client etc."""
    import http_caller

    return http_caller


def call_api_stream(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
) -> Generator[str, None, None]:
    """Stream chat completion chunks synchronously."""
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if hc.health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooling down", status_code=503)

    headers = hc._build_headers(cfg, key=selected_key)
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, stream=True)
    timeout = cfg.get("timeout", 60)
    fmt = cfg["fmt"]
    started = time.time()
    _enforce_https_scheme(cfg["url"], backend)

    total_text_holder: list[str] = []
    try:
        with hc._build_client(backend, timeout) as client:
            with client.stream("POST", cfg["url"], content=body, headers=headers) as resp:
                resp.raise_for_status()
                yield from _stream_parse_lines(
                    resp.iter_lines(),
                    fmt,
                    backend,
                    hc.health_tracker,
                    key_provider,
                    selected_key,
                    total_text_holder,
                )
        total_text = total_text_holder[0] if total_text_holder else ""
        _record_stream_success(hc, backend, key_provider, selected_key, total_text, started)
    except GeneratorExit:
        raise
    except (BackendError, httpx.HTTPStatusError, Exception) as exc:
        _record_stream_error(hc, backend, key_provider, selected_key, exc)


async def call_api_stream_async(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
) -> AsyncIterator[str]:
    """Stream chat completion chunks asynchronously."""
    hc = _caller()
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    selected_key, key_provider = hc._select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f"{backend} unavailable (no key)", status_code=404)
    if hc.health_tracker.is_cooled_down(backend):
        raise BackendError(f"{backend} is cooling down", status_code=503)

    headers = hc._build_headers(cfg, key=selected_key)
    body = hc._build_body(cfg, messages, max_tokens, system_prompt, ide, stream=True)
    timeout = cfg.get("timeout", 60)
    fmt = cfg["fmt"]
    started = time.time()
    _enforce_https_scheme(cfg["url"], backend)

    total_text_holder: list[str] = []
    try:
        async with hc._build_async_client(backend, timeout) as client:
            async with client.stream("POST", cfg["url"], content=body, headers=headers) as resp:
                resp.raise_for_status()
                async for chunk in _stream_parse_lines_async(
                    resp.aiter_lines(),
                    fmt,
                    backend,
                    hc.health_tracker,
                    key_provider,
                    selected_key,
                    total_text_holder,
                ):
                    yield chunk
        total_text = total_text_holder[0] if total_text_holder else ""
        _record_stream_success(hc, backend, key_provider, selected_key, total_text, started)
    except (asyncio.CancelledError, GeneratorExit):
        raise
    except (BackendError, httpx.HTTPStatusError, Exception) as exc:
        _record_stream_error(hc, backend, key_provider, selected_key, exc, "async ")
