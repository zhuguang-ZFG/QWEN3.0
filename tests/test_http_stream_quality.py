"""Tests for http_stream quality metrics and disconnect handling (H3/H4)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

import http_caller


BACKEND_CFG = {
    "url": "https://test.com/v1/chat/completions",
    "key": "sk-test",
    "model": "test-model",
    "fmt": "openai",
    "timeout": 10,
}


class _SyncStreamClient:
    def __init__(self, lines: list[str]):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        parent = self

        class _Ctx:
            def __enter__(self_inner):
                return parent

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()

    def raise_for_status(self):
        return None

    def iter_lines(self):
        yield from self.lines


class _AsyncStreamClient:
    def __init__(self, lines: list[str], block_after: int | None = None):
        self.lines = lines
        self.block_after = block_after

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        parent = self

        class _Ctx:
            async def __aenter__(self_inner):
                return parent

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for i, line in enumerate(self.lines):
            if self.block_after is not None and i >= self.block_after:
                await asyncio.Event().wait()
            yield line


@pytest.fixture
def stream_lines():
    content = "hello world"
    line = "data: " + json.dumps({"choices": [{"delta": {"content": content}}]})
    return [line, "data: [DONE]"], content


@patch("http_caller._select_key", return_value=("sk-test", "test-provider"))
@patch("http_caller._build_client")
@patch("http_caller.health_tracker")
def test_call_api_stream_records_real_response_quality(mock_ht, mock_build_client, _mock_key, stream_lines):
    mock_ht.is_cooled_down.return_value = False
    lines, content = stream_lines
    mock_build_client.return_value = _SyncStreamClient(lines)

    with patch.dict(http_caller.BACKENDS, {"stream_backend": dict(BACKEND_CFG)}):
        chunks = list(http_caller.call_api_stream("stream_backend", [{"role": "user", "content": "hi"}]))

    assert "".join(chunks) == content
    mock_ht.record_success.assert_called_once()
    mock_ht.record_response_quality.assert_called_once_with("stream_backend", len(content))
    mock_ht.record_failure.assert_not_called()


@patch("http_caller._select_key", return_value=("sk-test", "test-provider"))
@patch("http_caller._build_client")
@patch("http_caller.health_tracker")
def test_call_api_stream_generator_exit_does_not_record_failure(mock_ht, mock_build_client, _mock_key, stream_lines):
    mock_ht.is_cooled_down.return_value = False
    lines, _content = stream_lines
    mock_build_client.return_value = _SyncStreamClient(lines)

    with patch.dict(http_caller.BACKENDS, {"stream_backend": dict(BACKEND_CFG)}):
        gen = http_caller.call_api_stream("stream_backend", [{"role": "user", "content": "hi"}])
        try:
            next(gen)
        finally:
            gen.close()

    mock_ht.record_failure.assert_not_called()


@patch("http_caller._select_key", return_value=("sk-test", "test-provider"))
@patch("http_caller._build_async_client")
@patch("http_caller.health_tracker")
def test_call_api_stream_async_records_real_response_quality(mock_ht, mock_build_async_client, _mock_key, stream_lines):
    mock_ht.is_cooled_down.return_value = False
    lines, content = stream_lines
    mock_build_async_client.return_value = _AsyncStreamClient(lines)

    async def _run():
        with patch.dict(http_caller.BACKENDS, {"stream_backend": dict(BACKEND_CFG)}):
            return [
                chunk
                async for chunk in http_caller.call_api_stream_async(
                    "stream_backend", [{"role": "user", "content": "hi"}]
                )
            ]

    chunks = asyncio.run(_run())
    assert "".join(chunks) == content
    mock_ht.record_success.assert_called_once()
    mock_ht.record_response_quality.assert_called_once_with("stream_backend", len(content))
    mock_ht.record_failure.assert_not_called()


@patch("http_caller._select_key", return_value=("sk-test", "test-provider"))
@patch("http_caller._build_async_client")
@patch("http_caller.health_tracker")
def test_call_api_stream_async_cancel_does_not_record_failure(
    mock_ht, mock_build_async_client, _mock_key, stream_lines
):
    mock_ht.is_cooled_down.return_value = False
    lines, _content = stream_lines
    mock_build_async_client.return_value = _AsyncStreamClient(lines, block_after=1)

    async def _run():
        with patch.dict(http_caller.BACKENDS, {"stream_backend": dict(BACKEND_CFG)}):
            async for chunk in http_caller.call_api_stream_async("stream_backend", [{"role": "user", "content": "hi"}]):
                return chunk
        return None

    async def _cancel_after_first():
        task = asyncio.create_task(_run())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_cancel_after_first())
    mock_ht.record_failure.assert_not_called()
