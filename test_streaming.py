"""Tests for streaming.bridge_stream and streaming.speculative_stream.

These tests intentionally run async generators through asyncio.run() so the
suite does not depend on pytest-asyncio being installed in the local router
environment.
"""

import asyncio

import pytest

import streaming


def _mock_call_stream(backend, msgs, max_tokens, ide):
    yield "Hello"
    yield " world"
    yield "!"


def _mock_call_stream_empty(backend, msgs, max_tokens, ide):
    yield from ()


def _mock_call_api(backend, msgs, max_tokens, ide):
    return f"Answer from {backend}"


def _mock_call_api_fail(backend, msgs, max_tokens, ide):
    raise Exception("backend down")


def _mock_predict(query):
    return "longcat_chat"


def _mock_select(query, system_prompt, ide, messages):
    return "longcat_chat", messages


@pytest.fixture
def mock_deps():
    return {
        "call_stream_fn": _mock_call_stream,
        "call_fn": _mock_call_api,
        "predict_fn": _mock_predict,
        "select_fn": _mock_select,
    }


async def _collect_async(async_iterable):
    items = []
    async for item in async_iterable:
        items.append(item)
    return items


def test_bridge_stream_yields_chunks(mock_deps):
    chunks = asyncio.run(_collect_async(streaming.bridge_stream(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_fn=mock_deps["call_stream_fn"],
        call_fn=mock_deps["call_fn"],
    )))

    assert len(chunks) == 3
    assert "".join(chunks) == "Hello world!"


def test_bridge_stream_fallback_on_empty(mock_deps):
    chunks = asyncio.run(_collect_async(streaming.bridge_stream(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_fn=_mock_call_stream_empty,
        call_fn=mock_deps["call_fn"],
    )))

    assert len(chunks) == 1
    assert "Answer from longcat_chat" in chunks[0]


def test_bridge_stream_fallback_when_both_fail(mock_deps):
    chunks = asyncio.run(_collect_async(streaming.bridge_stream(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_fn=_mock_call_stream_empty,
        call_fn=_mock_call_api_fail,
    )))

    assert len(chunks) == 0


def test_speculative_stream_prediction_correct(mock_deps):
    results = asyncio.run(_collect_async(streaming.speculative_stream(
        "debug this",
        [{"role": "user", "content": "debug"}],
        4096,
        "unknown",
        predict_fn=mock_deps["predict_fn"],
        select_fn=mock_deps["select_fn"],
        call_stream_fn=mock_deps["call_stream_fn"],
        call_fn=mock_deps["call_fn"],
    )))

    assert all(backend == "longcat_chat" for backend, _ in results)
    assert len(results) == 3


def test_speculative_stream_prediction_wrong_switches(mock_deps):
    call_order = []

    def _select_different(*args):
        return "deepseek_flash", [{"role": "user", "content": "debug"}]

    def _stream_predicted(backend, msgs, mt, ide):
        call_order.append(("stream", backend))
        yield "partial..."

    results = asyncio.run(_collect_async(streaming.speculative_stream(
        "debug this",
        [{"role": "user", "content": "debug"}],
        4096,
        "unknown",
        predict_fn=mock_deps["predict_fn"],
        select_fn=_select_different,
        call_stream_fn=_stream_predicted,
        call_fn=mock_deps["call_fn"],
    )))

    assert len(results) > 0
    assert call_order == [("stream", "longcat_chat")]
