"""Tests for routes/stream_handlers.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import routes.stream_handlers as sh


async def _async_gen(items):
    for item in items:
        yield item


@patch.object(sh.streaming_mod, "bridge_stream")
@pytest.mark.asyncio
async def test_real_stream_chunks_bridges_sync_stream(mock_bridge):
    mock_bridge.return_value = _async_gen(["chunk1", "chunk2"])
    chunks = [c async for c in sh.real_stream_chunks("backend", [{"role": "user", "content": "hi"}])]
    assert chunks == ["chunk1", "chunk2"]
    mock_bridge.assert_called_once()
    _, args, kwargs = mock_bridge.mock_calls[0]
    assert args[0] == "backend"
    assert kwargs.get("call_stream_fn") is sh.v3_call_stream
    assert kwargs.get("call_fn") is sh.v3_call_api


@patch.object(sh.streaming_mod, "bridge_stream_async")
@pytest.mark.asyncio
async def test_real_stream_chunks_async_bridges_async_stream(mock_bridge):
    mock_bridge.return_value = _async_gen(["a", "b"])
    chunks = [c async for c in sh.real_stream_chunks_async("backend", [])]
    assert chunks == ["a", "b"]
    mock_bridge.assert_called_once()
    _, _, kwargs = mock_bridge.mock_calls[0]
    assert kwargs.get("call_stream_async_fn") is sh.v3_call_stream_async
    assert kwargs.get("call_api_async_fn") is sh.v3_call_api_async


@patch.object(sh.streaming_mod, "speculative_stream")
@pytest.mark.asyncio
async def test_speculative_stream_chunks_delegates(mock_spec):
    mock_spec.return_value = _async_gen([("backend", "hello"), ("backend", "world")])
    chunks = [c async for c in sh.speculative_stream_chunks("hi", [], preferred_backend="fast")]
    assert chunks == [("backend", "hello"), ("backend", "world")]
    mock_spec.assert_called_once()
    _, args, kwargs = mock_spec.mock_calls[0]
    assert args[0] == "hi"
    assert args[1] == []
    assert kwargs.get("system_prompt") == ""
    assert kwargs.get("call_stream_fn") is sh.v3_call_stream
