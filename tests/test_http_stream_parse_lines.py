"""Focused unit tests for http_stream parse-line helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from http_errors import BackendError
from http_stream import (
    _stream_parse_lines,
    _stream_parse_lines_async,
    StreamIdentitySanitizer,
)


def _line(content: str) -> str:
    """Build an OpenAI-format SSE data line."""
    return "data: " + json.dumps({"choices": [{"delta": {"content": content}}]})


async def _collect_async(aiter):
    return [chunk async for chunk in aiter]


def _health_tracker():
    return MagicMock()


def test_normal_sse_stream_yields_cleaned_chunks_sync():
    lines = [
        _line("Hello "),
        _line("world!"),
        "data: [DONE]",
    ]
    ht = _health_tracker()
    result = list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    assert result == ["Hello", "world!"]


@pytest.mark.asyncio
async def test_normal_sse_stream_yields_cleaned_chunks_async():
    lines = [
        _line("Hello "),
        _line("world!"),
        "data: [DONE]",
    ]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    result = await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    assert result == ["Hello", "world!"]


def test_empty_stream_yields_nothing_sync():
    ht = _health_tracker()
    result = list(_stream_parse_lines([], "openai", "test-backend", ht, None, None))
    assert result == []
    ht.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_empty_stream_yields_nothing_async():
    ht = _health_tracker()

    async def _aiter():
        if False:
            yield

    result = await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    assert result == []
    ht.record_failure.assert_not_called()


def test_backend_error_in_initial_buffer_raises_sync():
    lines = [_line("服务繁忙，请稍后再试")]
    ht = _health_tracker()
    with pytest.raises(BackendError):
        list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    ht.record_failure.assert_called()


@pytest.mark.asyncio
async def test_backend_error_in_initial_buffer_raises_async():
    lines = [_line("服务繁忙，请稍后再试")]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    with pytest.raises(BackendError):
        await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    ht.record_failure.assert_called()


def test_backend_error_after_flush_raises_sync():
    """Error text arriving after the 200-char flush threshold must raise."""
    lines = [
        _line("a" * 100),
        _line("b" * 110),
        _line("服务繁忙，请稍后再试"),
        "data: [DONE]",
    ]
    ht = _health_tracker()
    with pytest.raises(BackendError):
        list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    ht.record_failure.assert_called()


@pytest.mark.asyncio
async def test_backend_error_after_flush_raises_async():
    lines = [
        _line("a" * 100),
        _line("b" * 110),
        _line("服务繁忙，请稍后再试"),
        "data: [DONE]",
    ]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    with pytest.raises(BackendError):
        await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    ht.record_failure.assert_called()


def test_done_line_is_ignored_sync():
    lines = ["data: [DONE]"]
    ht = _health_tracker()
    result = list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    assert result == []


@pytest.mark.asyncio
async def test_done_line_is_ignored_async():
    lines = ["data: [DONE]"]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    result = await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    assert result == []


def test_non_data_lines_are_ignored_sync():
    lines = [
        "",
        "event: message",
        ": ping",
        _line("visible"),
        "data: [DONE]",
    ]
    ht = _health_tracker()
    result = list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    assert result == ["visible"]


@pytest.mark.asyncio
async def test_non_data_lines_are_ignored_async():
    lines = [
        "",
        "event: message",
        ": ping",
        _line("visible"),
        "data: [DONE]",
    ]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    result = await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    assert result == ["visible"]


def test_sanitizer_tail_is_flushed_at_end_sync():
    """Long post-flush output leaves bytes in the sanitizer; flush them at end."""
    chunk = "x" * 200
    lines = [
        _line(chunk),
        _line("tail"),
        "data: [DONE]",
    ]
    ht = _health_tracker()
    result = list(_stream_parse_lines(lines, "openai", "test-backend", ht, None, None))
    joined = "".join(result)
    assert joined == chunk + "tail"


@pytest.mark.asyncio
async def test_sanitizer_tail_is_flushed_at_end_async():
    chunk = "x" * 200
    lines = [
        _line(chunk),
        _line("tail"),
        "data: [DONE]",
    ]
    ht = _health_tracker()

    async def _aiter():
        for line in lines:
            yield line

    result = await _collect_async(_stream_parse_lines_async(_aiter(), "openai", "test-backend", ht, None, None))
    joined = "".join(result)
    assert joined == chunk + "tail"


def test_stream_identity_sanitizer_used_by_helpers():
    """Sanitizer class is available and behaves as expected."""
    sanitizer = StreamIdentitySanitizer("test-backend")
    assert sanitizer is not None
    assert sanitizer.feed("x" * 96) == ""
    flushed = sanitizer.flush()
    assert flushed == "x" * 96
