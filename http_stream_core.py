"""Internal SSE streaming helpers used by http_stream."""

from __future__ import annotations

import logging
import time
from typing import AsyncIterator, Generator

import httpx
from response_cleaner import StreamIdentitySanitizer, clean_response, _is_backend_error

from http_errors import BackendError, _extract_code, _extract_retry_after
from http_response import _parse_sse_chunk

_log = logging.getLogger(__name__)


def _maybe_raise_backend_error(total_text: str, backend: str, health_tracker) -> None:
    """Detect backend error text and raise BackendError."""
    if _is_backend_error(total_text):
        health_tracker.record_failure(backend, error_code=429, error_text=total_text)
        raise BackendError(f"{backend} error: {total_text[:60]}", status_code=429)


def _flush_initial_buffer(pending_chunks: list[str], backend: str) -> tuple[str, StreamIdentitySanitizer]:
    """Concatenate pending chunks, sanitize, and create a stream sanitizer."""
    buffered = "".join(pending_chunks)
    cleaned = clean_response(buffered, backend)
    sanitizer = StreamIdentitySanitizer(backend)
    return cleaned, sanitizer


def _flush_sanitizer_tail(sanitizer) -> str | None:
    """Flush sanitizer tail text, if any."""
    if sanitizer is None:
        return None
    tail = sanitizer.flush()
    return tail if tail else None


def _clean_chunk(chunk: str, backend: str) -> str:
    """Remove data: prefix, strip, and apply response cleaning if needed."""
    line = chunk.strip()
    if line.startswith("data: "):
        line = line[6:]
    if line == "[DONE]":
        return ""
    return clean_response(line.strip(), backend)


def _handle_empty_or_unflushed_buffer(
    pending_chunks: list[str], total_text: str, backend: str, health_tracker
) -> list[str]:
    """Detect backend error/empty stream and return cleaned chunks to yield."""
    if not total_text:
        return []
    if _is_backend_error(total_text):
        health_tracker.record_failure(backend, error_code=429, error_text=total_text)
        raise BackendError(f"{backend} returned error: {total_text[:60]}", status_code=429)
    return [cleaned for chunk in pending_chunks if (cleaned := _clean_chunk(chunk, backend))]


def _stream_parse_lines(
    lines,
    fmt: str,
    backend: str,
    health_tracker,
    key_provider,
    selected_key,
    total_text_out: list[str] | None = None,
) -> Generator[str, None, None]:
    """Parse SSE lines, yield cleaned text chunks. Raises BackendError on error."""
    pending_chunks: list[str] = []
    total_text = ""
    flushed = False
    stream_sanitizer: StreamIdentitySanitizer | None = None

    for line in lines:
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
            _maybe_raise_backend_error(text, backend, health_tracker)
            cleaned_out = stream_sanitizer.feed(text)
            if cleaned_out:
                yield cleaned_out
        else:
            pending_chunks.append(text)
            if len(total_text) > 200:
                _maybe_raise_backend_error(total_text, backend, health_tracker)
                cleaned, stream_sanitizer = _flush_initial_buffer(pending_chunks, backend)
                if cleaned:
                    yield cleaned
                pending_chunks = []
                flushed = True

    if flushed:
        tail = _flush_sanitizer_tail(stream_sanitizer)
        if tail:
            yield tail
    else:
        for chunk in _handle_empty_or_unflushed_buffer(pending_chunks, total_text, backend, health_tracker):
            yield chunk

    if total_text_out is not None:
        total_text_out.append(total_text)


def _record_stream_success(hc, backend, key_provider, selected_key, total_text, started):
    latency_ms = int((time.time() - started) * 1000)
    hc.health_tracker.record_success(backend, latency_ms)
    hc._report_key_result(key_provider, selected_key, True)
    hc.health_tracker.record_response_quality(backend, len(total_text) if total_text else 0)


def _record_stream_error(hc, backend, key_provider, selected_key, exc, label: str = ""):
    if isinstance(exc, BackendError):
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=exc.status_code or 0,
            retry_after=0,
        )
        raise exc
    if isinstance(exc, httpx.HTTPStatusError):
        error_code = exc.response.status_code
        hc.health_tracker.record_failure(backend, error_code=error_code, error_text=str(exc))
        hc._report_key_result(
            key_provider,
            selected_key,
            False,
            error_code=error_code,
            retry_after=_extract_retry_after(exc),
        )
        raise BackendError(str(exc), status_code=error_code) from exc

    error_code = _extract_code(exc)
    hc.health_tracker.record_failure(backend, error_code=error_code, error_text=str(exc))
    hc._report_key_result(
        key_provider,
        selected_key,
        False,
        error_code=error_code or 0,
        retry_after=_extract_retry_after(exc),
    )
    _log.warning("stream %s%serror: %s", backend, label, exc, exc_info=True)
    raise BackendError(str(exc), status_code=error_code) from exc


async def _stream_parse_lines_async(
    aiter_lines,
    fmt: str,
    backend: str,
    health_tracker,
    key_provider,
    selected_key,
    total_text_out: list[str] | None = None,
) -> AsyncIterator[str]:
    """Async version: parse SSE lines from an async iterator."""
    pending_chunks: list[str] = []
    total_text = ""
    flushed = False
    stream_sanitizer: StreamIdentitySanitizer | None = None

    async for line in aiter_lines:
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
            _maybe_raise_backend_error(text, backend, health_tracker)
            cleaned_out = stream_sanitizer.feed(text)
            if cleaned_out:
                yield cleaned_out
        else:
            pending_chunks.append(text)
            if len(total_text) > 200:
                _maybe_raise_backend_error(total_text, backend, health_tracker)
                cleaned, stream_sanitizer = _flush_initial_buffer(pending_chunks, backend)
                if cleaned:
                    yield cleaned
                pending_chunks = []
                flushed = True

    if flushed:
        tail = _flush_sanitizer_tail(stream_sanitizer)
        if tail:
            yield tail
    else:
        for chunk in _handle_empty_or_unflushed_buffer(pending_chunks, total_text, backend, health_tracker):
            yield chunk

    if total_text_out is not None:
        total_text_out.append(total_text)
