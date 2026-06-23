"""Tests for routes/v3_adapters.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import routes.v3_adapters as v3


@pytest.fixture(autouse=True)
def _patch_classify_scenario():
    with patch.object(v3, "classify_scenario", return_value="chat"):
        yield


def make_route_result(answer="ok", backend="test", ms=12.0, fallback_used=False):
    return SimpleNamespace(answer=answer, backend=backend, ms=ms, fallback_used=fallback_used)


def make_pick_result(backend="test", messages=None):
    return SimpleNamespace(backend=backend, messages=messages or [])


@patch.object(v3.routing_engine, "route")
def test_v3_route_returns_adapter_dict(mock_route):
    mock_route.return_value = make_route_result(answer="hello", backend="longcat", ms=42.0, fallback_used=True)
    result = v3.v3_route("hi", [{"role": "user", "content": "hi"}])
    assert result == {
        "answer": "hello",
        "backend": "longcat",
        "total_ms": 42.0,
        "fallback_used": True,
    }
    mock_route.assert_called_once()
    _, kwargs = mock_route.call_args
    assert kwargs["fmt"] == "openai"
    assert kwargs["ide_source"] == ""


@patch.object(v3.routing_engine, "pick_backend")
def test_v3_predict_returns_backend(mock_pick):
    mock_pick.return_value = make_pick_result(backend="groq")
    assert v3.v3_predict("hi", [{"role": "user", "content": "hi"}]) == "groq"


@patch.object(v3.routing_engine, "pick_backend")
def test_v3_predict_fallback_on_exception(mock_pick):
    mock_pick.side_effect = RuntimeError("boom")
    assert v3.v3_predict("hi", []) == v3._FALLBACK_BACKEND


@patch.object(v3.routing_engine, "pick_backend")
def test_v3_select_returns_backend_and_messages(mock_pick):
    msgs = [{"role": "user", "content": "hi"}]
    mock_pick.return_value = make_pick_result(backend="groq", messages=msgs)
    backend, messages = v3.v3_select("hi", "", "", msgs)
    assert backend == "groq"
    assert messages == msgs


@patch.object(v3.routing_engine, "pick_backend")
def test_v3_select_fallback_on_exception(mock_pick):
    mock_pick.side_effect = ValueError("bad")
    msgs = [{"role": "user", "content": "hi"}]
    backend, messages = v3.v3_select("hi", "", "", msgs)
    assert backend == v3._FALLBACK_BACKEND
    assert messages == msgs


@patch.object(v3.http_caller, "call_api_stream")
def test_v3_call_stream_uses_stream(mock_stream):
    mock_stream.return_value = iter(["chunk1", "chunk2"])
    messages = [{"role": "user", "content": "hi"}]
    chunks = list(v3.v3_call_stream("backend", messages, 100, "vscode"))
    assert chunks == ["chunk1", "chunk2"]
    mock_stream.assert_called_once()
    _, args, kwargs = mock_stream.mock_calls[0]
    assert args[0] == "backend"
    assert args[2] == 100
    assert kwargs.get("ide") == "vscode"
    assert "system_prompt" in kwargs


@patch.object(v3.http_caller, "call_api")
def test_v3_call_api_non_stream(mock_call):
    mock_call.return_value = "answer"
    messages = [{"role": "user", "content": "hi"}]
    assert v3.v3_call_api("backend", messages, 50, "vscode") == "answer"
    mock_call.assert_called_once()


@patch.object(v3.http_caller, "call_api")
def test_v3_call_api_fake_stream_backend(mock_call):
    mock_call.return_value = "full answer"
    messages = [{"role": "user", "content": "hi"}]
    chunks = list(v3.v3_call_stream("deepseek_free", messages, 50, "vscode"))
    assert chunks == ["full answer"]
    mock_call.assert_called_once()


def test_fake_stream_chunks_text():
    text = "1234567890" * 4  # 40 chars
    chunks = list(v3.fake_stream(text, chunk_size=10))
    assert "".join(chunks) == text
    assert len(chunks) == 4


@pytest.mark.asyncio
@patch.object(v3.http_caller, "call_api_stream_async")
async def test_v3_call_stream_async(mock_stream_async):
    async def _gen():
        yield "a"
        yield "b"

    mock_stream_async.return_value = _gen()
    messages = [{"role": "user", "content": "hi"}]
    chunks = [c async for c in v3.v3_call_stream_async("backend", messages, 10, "vscode")]
    assert chunks == ["a", "b"]


@pytest.mark.asyncio
@patch.object(v3.http_caller, "call_api_async")
async def test_v3_call_api_async(mock_call_async):
    mock_call_async.return_value = "async answer"
    messages = [{"role": "user", "content": "hi"}]
    result = await v3.v3_call_api_async("backend", messages, 10, "vscode")
    assert result == "async answer"
