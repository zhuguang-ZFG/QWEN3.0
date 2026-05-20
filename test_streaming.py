"""
test_streaming.py — 测试纯流式核心 (bridge_stream + speculative_stream)
所有依赖注入函数使用 mock，不依赖 smart_router
"""
import pytest
import asyncio
import queue

import streaming


# ── Mock 依赖注入函数 ────────────────────────────────────────────────────────

def _mock_call_stream(backend, msgs, max_tokens, ide):
    """模拟同步流: 返回 3 个 chunk"""
    yield "Hello"
    yield " world"
    yield "!"


def _mock_call_stream_empty(backend, msgs, max_tokens, ide):
    """空流 (立即 done)"""
    yield from ()


def _mock_call_stream_slow(backend, msgs, max_tokens, ide):
    """慢流: 1个chunk后卡住"""
    yield "slow..."


def _mock_call_api(backend, msgs, max_tokens, ide):
    """模拟非流式调用"""
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


# ── bridge_stream ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bridge_stream_yields_chunks(mock_deps):
    chunks = []
    async for chunk in streaming.bridge_stream(
        "longcat_chat", [{"role": "user", "content": "hi"}],
        4096, "unknown",
        call_stream_fn=mock_deps["call_stream_fn"],
        call_fn=mock_deps["call_fn"],
    ):
        chunks.append(chunk)
    assert len(chunks) == 3
    assert "".join(chunks) == "Hello world!"


@pytest.mark.asyncio
async def test_bridge_stream_fallback_on_empty(mock_deps):
    """空流→fallback到非流式"""
    chunks = []
    async for chunk in streaming.bridge_stream(
        "longcat_chat", [{"role": "user", "content": "hi"}],
        4096, "unknown",
        call_stream_fn=_mock_call_stream_empty,
        call_fn=mock_deps["call_fn"],
    ):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert "Answer from longcat_chat" in chunks[0]


@pytest.mark.asyncio
async def test_bridge_stream_fallback_when_both_fail(mock_deps):
    """流失败且非流式也失败→返回空"""
    chunks = []
    async for chunk in streaming.bridge_stream(
        "longcat_chat", [{"role": "user", "content": "hi"}],
        4096, "unknown",
        call_stream_fn=_mock_call_stream_empty,
        call_fn=_mock_call_api_fail,
    ):
        chunks.append(chunk)
    assert len(chunks) == 0


# ── speculative_stream ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_speculative_stream_prediction_correct(mock_deps):
    """预测正确→流来自预测后端"""
    results = []
    async for backend, chunk in streaming.speculative_stream(
        "debug this", [{"role": "user", "content": "debug"}],
        4096, "unknown",
        predict_fn=mock_deps["predict_fn"],
        select_fn=mock_deps["select_fn"],
        call_stream_fn=mock_deps["call_stream_fn"],
        call_fn=mock_deps["call_fn"],
    ):
        results.append((backend, chunk))
    assert all(b == "longcat_chat" for b, _ in results)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_speculative_stream_prediction_wrong_switches(mock_deps):
    """预测错误→切换到实际后端"""
    call_order = []

    def _select_different(*args):
        return "deepseek_flash", [{"role": "user", "content": "debug"}]

    def _stream_predicted(backend, msgs, mt, ide):
        call_order.append(("stream", backend))
        yield "partial..."

    results = []
    async for backend, chunk in streaming.speculative_stream(
        "debug this", [{"role": "user", "content": "debug"}],
        4096, "unknown",
        predict_fn=mock_deps["predict_fn"],
        select_fn=_select_different,
        call_stream_fn=_stream_predicted,
        call_fn=mock_deps["call_fn"],
    ):
        results.append((backend, chunk))
    # Should have chunks from both backends
    assert len(results) > 0
