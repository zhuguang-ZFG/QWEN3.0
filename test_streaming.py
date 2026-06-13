"""Tests for streaming.bridge_stream and streaming.speculative_stream.

These tests intentionally run async generators through asyncio.run() so the
suite does not depend on pytest-asyncio being installed in the local router
environment.
"""

import asyncio

import pytest

import speculative
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


def _mock_predict(query, messages, system_prompt="", ide=""):
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


async def _mock_call_stream_async(backend, msgs, max_tokens, ide):
    yield "Hello"
    yield " async"


async def _mock_call_stream_async_empty(backend, msgs, max_tokens, ide):
    if False:
        yield ""


async def _mock_call_stream_async_slow_first_chunk(backend, msgs, max_tokens, ide):
    await asyncio.sleep(0.05)
    yield "too late"


async def _mock_call_api_async(backend, msgs, max_tokens, ide):
    return f"Async answer from {backend}"


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


def test_bridge_stream_async_yields_chunks():
    chunks = asyncio.run(_collect_async(streaming.bridge_stream_async(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_async_fn=_mock_call_stream_async,
        call_api_async_fn=_mock_call_api_async,
    )))

    assert "".join(chunks) == "Hello async"


def test_bridge_stream_async_fallback_on_empty():
    chunks = asyncio.run(_collect_async(streaming.bridge_stream_async(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_async_fn=_mock_call_stream_async_empty,
        call_api_async_fn=_mock_call_api_async,
    )))

    assert chunks == ["Async answer from longcat_chat"]


def test_bridge_stream_async_first_chunk_timeout_falls_back():
    chunks = asyncio.run(_collect_async(streaming.bridge_stream_async(
        "longcat_chat",
        [{"role": "user", "content": "hi"}],
        4096,
        "unknown",
        call_stream_async_fn=_mock_call_stream_async_slow_first_chunk,
        call_api_async_fn=_mock_call_api_async,
        first_chunk_timeout=0.001,
    )))

    assert chunks == ["Async answer from longcat_chat"]


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


def test_speculative_stream_uses_async_native_path(mock_deps):
    async def _stream_async(backend, msgs, max_tokens, ide):
        yield f"async from {backend}"

    async def _api_async(backend, msgs, max_tokens, ide):
        return f"fallback from {backend}"

    results = asyncio.run(_collect_async(streaming.speculative_stream(
        "hello",
        [{"role": "user", "content": "hello"}],
        4096,
        "unknown",
        predict_fn=mock_deps["predict_fn"],
        select_fn=mock_deps["select_fn"],
        call_stream_fn=mock_deps["call_stream_fn"],
        call_fn=mock_deps["call_fn"],
        call_stream_async_fn=_stream_async,
        call_api_async_fn=_api_async,
    )))

    assert results == [("longcat_chat", "async from longcat_chat")]


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


def test_speculative_call_async_waits_past_invalid_first_result(monkeypatch):
    monkeypatch.setattr(speculative.health_tracker, "record_success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(speculative.budget_manager, "record_usage", lambda *_args, **_kwargs: None)

    async def _call(backend, _messages, _max_tokens):
        if backend == "fast_bad":
            await asyncio.sleep(0.001)
            return "short"
        await asyncio.sleep(0.01)
        return "valid response from slower backend"

    backend, answer, _latency = asyncio.run(speculative.speculative_call_async(
        ["fast_bad", "slow_good"],
        _call,
        [{"role": "user", "content": "hi"}],
        max_parallel=2,
        timeout_sec=0.1,
    ))

    assert backend == "slow_good"
    assert answer == "valid response from slower backend"


def test_speculative_call_sync_facade_works_inside_running_loop(monkeypatch):
    monkeypatch.setattr(speculative.health_tracker, "record_success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(speculative.budget_manager, "record_usage", lambda *_args, **_kwargs: None)

    def _call(backend, _messages, _max_tokens):
        return f"valid response from {backend}"

    async def _inside_loop():
        return speculative.speculative_call(
            ["sync_backend"],
            _call,
            [{"role": "user", "content": "hi"}],
            max_parallel=1,
            timeout_sec=0.1,
        )

    backend, answer, _latency = asyncio.run(_inside_loop())

    assert backend == "sync_backend"
    assert answer == "valid response from sync_backend"
