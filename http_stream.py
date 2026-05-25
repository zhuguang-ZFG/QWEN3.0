"""Sync and async SSE streaming for http_caller (CQ-014 slice 8)."""

from __future__ import annotations

import os
import sys
import time
from typing import AsyncIterator, Generator

import httpx
from response_cleaner import StreamIdentitySanitizer, clean_response, _is_backend_error

from backends import BACKENDS
from http_errors import BackendError, _extract_code, _extract_retry_after
from http_response import _parse_sse_chunk

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"


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

    try:
        with hc._build_client(backend, timeout) as client:
            pending_chunks: list[str] = []
            total_text = ""
            flushed = False
            stream_sanitizer: StreamIdentitySanitizer | None = None

            with client.stream("POST", cfg["url"], content=body, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    text = _parse_sse_chunk(data_str, fmt)
                    if not text:
                        continue
                    total_text += text
                    if flushed:
                        if stream_sanitizer is None:
                            stream_sanitizer = StreamIdentitySanitizer(backend)
                        cleaned_out = stream_sanitizer.feed(text)
                        if cleaned_out:
                            yield cleaned_out
                    else:
                        pending_chunks.append(text)
                        if len(total_text) > 200:
                            if _is_backend_error(total_text):
                                hc.health_tracker.record_failure(
                                    backend, error_code=429, error_text=total_text
                                )
                                raise BackendError(
                                    f"{backend} error: {total_text[:60]}",
                                    status_code=429,
                                )
                            buffered = "".join(pending_chunks)
                            cleaned = clean_response(buffered, backend)
                            if cleaned:
                                yield cleaned
                            pending_chunks = []
                            flushed = True
                            stream_sanitizer = StreamIdentitySanitizer(backend)

        if flushed and stream_sanitizer is not None:
            tail = stream_sanitizer.flush()
            if tail:
                yield tail

        if not flushed:
            if not total_text:
                hc.health_tracker.record_failure(
                    backend, error_code=502, error_text="empty stream"
                )
                raise BackendError(f"{backend} returned empty stream", status_code=502)
            if _is_backend_error(total_text):
                hc.health_tracker.record_failure(
                    backend, error_code=429, error_text=total_text
                )
                raise BackendError(
                    f"{backend} returned error: {total_text[:60]}",
                    status_code=429,
                )
            for chunk in pending_chunks:
                cleaned = clean_response(chunk, backend)
                if cleaned:
                    yield cleaned

        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        hc.health_tracker.record_response_quality(
            backend, len(total_text) if total_text else 0
        )

    except BackendError as exc:
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        hc.health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        hc.health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        if DEBUG:
            print(f"[STREAM] {backend} error: {exc}", file=sys.stderr)
        raise BackendError(str(exc), status_code=error_code) from exc


async def call_api_stream_async(
    backend: str,
    messages: list[dict],
    max_tokens: int = 4096,
    *,
    system_prompt: str = "",
    ide: str = "",
) -> AsyncIterator[str]:
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

    try:
        async with hc._build_async_client(backend, timeout) as client:
            pending_chunks: list[str] = []
            total_text = ""
            flushed = False
            stream_sanitizer: StreamIdentitySanitizer | None = None

            async with client.stream(
                "POST", cfg["url"], content=body, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    text = _parse_sse_chunk(data_str, fmt)
                    if not text:
                        continue
                    total_text += text
                    if flushed:
                        if stream_sanitizer is None:
                            stream_sanitizer = StreamIdentitySanitizer(backend)
                        cleaned_out = stream_sanitizer.feed(text)
                        if cleaned_out:
                            yield cleaned_out
                    else:
                        pending_chunks.append(text)
                        if len(total_text) > 200:
                            if _is_backend_error(total_text):
                                hc.health_tracker.record_failure(
                                    backend, error_code=429, error_text=total_text
                                )
                                raise BackendError(
                                    f"{backend} error: {total_text[:60]}",
                                    status_code=429,
                                )
                            buffered = "".join(pending_chunks)
                            cleaned_out = clean_response(buffered, backend)
                            if cleaned_out:
                                yield cleaned_out
                            pending_chunks = []
                            flushed = True
                            stream_sanitizer = StreamIdentitySanitizer(backend)

        if flushed and stream_sanitizer is not None:
            tail = stream_sanitizer.flush()
            if tail:
                yield tail

        if not flushed:
            if not total_text:
                hc.health_tracker.record_failure(
                    backend, error_code=502, error_text="empty stream"
                )
                raise BackendError(
                    f"{backend} returned empty stream", status_code=502
                )
            if _is_backend_error(total_text):
                hc.health_tracker.record_failure(
                    backend, error_code=429, error_text=total_text
                )
                raise BackendError(
                    f"{backend} returned error: {total_text[:60]}",
                    status_code=429,
                )
            for chunk in pending_chunks:
                cleaned_out = clean_response(chunk, backend)
                if cleaned_out:
                    yield cleaned_out

        latency_ms = int((time.time() - started) * 1000)
        hc.health_tracker.record_success(backend, latency_ms)
        hc._report_key_result(key_provider, selected_key, True)
        hc.health_tracker.record_response_quality(
            backend, len(total_text) if total_text else 0
        )

    except BackendError as exc:
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise
    except httpx.HTTPStatusError as exc:
        error_code = exc.response.status_code
        hc.health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc
    except Exception as exc:
        error_code = _extract_code(exc)
        hc.health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(exc)
        )
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code or 0,
            retry_after=_extract_retry_after(exc),
        )
        if DEBUG:
            print(f"[STREAM] {backend} async error: {exc}", file=sys.stderr)
        raise BackendError(str(exc), status_code=error_code) from exc
