"""Tests for routes/chat_stream.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import response_builder
import response_cleaner
import routes.chat_stream as cs


async def _async_gen(items):
    for item in items:
        yield item


@pytest.fixture(autouse=True)
def _reset_deps():
    cs.inject_deps(last_resort_call=lambda _msgs: "fallback", build_pollinations_url=lambda _p, _s: "http://img")
    yield
    cs.inject_deps(last_resort_call=None, build_pollinations_url=None)


@pytest.mark.asyncio
@patch.object(cs, "_resolve_image_content")
async def test_stream_response_image_branch(mock_image):
    mock_image.return_value = "![image](url)\n\ndesc"
    chunks = [c async for c in cs.stream_response("cid", "draw cat", False, use_thinking=False)]
    assert "![image](url)" in chunks[0]
    assert "desc" in chunks[0]
    assert chunks[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
@patch.object(cs, "_resolve_image_content", return_value=None)
@patch.object(cs, "_resolve_thinking_content")
@patch.object(cs, "stream_sentences")
async def test_stream_response_thinking_branch(mock_sentences, mock_thinking, _mock_image):
    mock_thinking.return_value = "thinking answer"
    mock_sentences.return_value = _async_gen(["chunk1", "done"])
    chunks = [c async for c in cs.stream_response("cid", "solve", False, use_thinking=True)]
    assert chunks == ["chunk1", "done"]
    mock_thinking.assert_called_once()


@pytest.mark.asyncio
@patch.object(cs, "_resolve_image_content", return_value=None)
@patch.object(cs, "_stream_orchestration")
async def test_stream_response_orchestration_branch(mock_orch, _mock_image):
    mock_orch.return_value = _async_gen(["o1", "o2"])
    chunks = [c async for c in cs.stream_response("cid", "plan", True, use_thinking=False)]
    assert chunks == ["o1", "o2"]
    mock_orch.assert_called_once()


@pytest.mark.asyncio
@patch.object(cs, "_resolve_image_content", return_value=None)
@patch.object(cs, "_stream_speculative")
async def test_stream_response_speculative_branch(mock_spec, _mock_image):
    mock_spec.return_value = _async_gen(["s1", "s2"])
    chunks = [c async for c in cs.stream_response("cid", "hi", False, prefer="fast")]
    assert chunks == ["s1", "s2"]
    mock_spec.assert_called_once()


@patch.object(cs, "_last_resort_call")
@patch.object(response_cleaner, "clean_response")
def test_ensure_content_uses_last_resort_when_blank(mock_clean, mock_last):
    mock_clean.return_value = ""
    mock_last.return_value = "last resort"
    assert cs._ensure_content("   ", [{"role": "user", "content": "hi"}]) == "last resort"


@patch.object(response_cleaner, "clean_response")
def test_ensure_content_returns_content_when_present(mock_clean):
    mock_clean.return_value = "cleaned"
    assert cs._ensure_content("raw", []) == "cleaned"


@patch.object(response_cleaner, "clean_response")
def test_ensure_fallback_content_handles_error_prefix(mock_clean):
    mock_clean.return_value = "[ERR] timeout"
    cs._last_resort_call = None
    assert cs._ensure_content("[ERR] timeout", [], allow_error_prefix=True) == cs.FALLBACK_MSG


@patch.object(cs.routing_intent, "detect_image_intent")
@pytest.mark.asyncio
async def test_resolve_image_content_returns_none_when_no_intent(mock_detect):
    mock_detect.return_value = (False, "")
    assert await cs._resolve_image_content("hi") is None


@patch.object(cs.routing_intent, "detect_image_intent")
@pytest.mark.asyncio
async def test_resolve_image_content_builds_markdown(mock_detect):
    mock_detect.return_value = (True, "a cat")
    result = await cs._resolve_image_content("draw cat")
    assert result.startswith("![image]")
    assert "http://img" in result


@pytest.mark.asyncio
@patch.object(cs, "thinking_route")
@patch.object(cs, "_authoritative_route")
async def test_resolve_thinking_content_prefers_thinking_route(mock_auth, mock_thinking):
    mock_thinking.return_value = {"answer": "thought"}
    result = await cs._resolve_thinking_content("q", [], sys_prompt_preview="", ide_source="", use_orchestration=False)
    assert result == "thought"
    mock_auth.assert_not_called()


@pytest.mark.asyncio
@patch.object(cs, "thinking_route", return_value=None)
@patch.object(cs, "_authoritative_route")
async def test_resolve_thinking_content_falls_back_to_authoritative(mock_auth, _mock_thinking):
    mock_auth.return_value = {"answer": "auth"}
    result = await cs._resolve_thinking_content("q", [], sys_prompt_preview="", ide_source="", use_orchestration=False)
    assert result == "auth"


@pytest.mark.asyncio
@patch.object(cs, "_authoritative_route")
async def test_resolve_authoritative_content_logs_and_returns_empty(mock_auth, caplog):
    mock_auth.side_effect = RuntimeError("boom")
    result = await cs._resolve_authoritative_content("q", [], sys_prompt_preview="", ide_source="")
    assert result == ""
    assert any("stream authoritative route failed" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
@patch.object(response_builder, "_split_sentences")
@patch.object(response_builder, "build_stream_chunk")
async def test_stream_sentences_yields_finish_markers(mock_build_chunk, mock_split):
    mock_split.return_value = ["Hello.", "World."]
    mock_build_chunk.side_effect = lambda _cid, text, finish=False: f"data: {text or '[DONE]'}\n\n"
    chunks = [c async for c in response_builder.stream_sentences("cid", "Hello. World.")]
    assert chunks == [
        "data: Hello.\n\n",
        "data: World.\n\n",
        "data: [DONE]\n\n",
        "data: [DONE]\n\n",
    ]


@pytest.mark.asyncio
@patch.object(cs, "_resolve_thinking_content", return_value="thought")
@patch.object(cs, "stream_sentences")
async def test_stream_thinking_response(mock_sentences, mock_thinking):
    mock_sentences.return_value = _async_gen(["c1", "done"])
    chunks = [
        c
        async for c in cs._stream_thinking_response(
            "cid", "q", [], sys_prompt_preview="", ide_source="", use_orchestration=False
        )
    ]
    assert chunks == ["c1", "done"]
    mock_thinking.assert_called_once()


@pytest.mark.asyncio
@patch.object(cs, "speculative_stream_chunks")
@patch.object(cs, "stream_sentences")
@patch.object(cs, "_resolve_authoritative_content", return_value="auth answer")
async def test_stream_speculative_fallback_when_no_chunks(
    mock_auth, mock_sentences, mock_spec
):
    mock_spec.return_value = _async_gen([])
    mock_sentences.return_value = _async_gen(["fallback chunk"])
    chunks = [
        c
        async for c in cs._stream_speculative(
            "q", [], "cid", sys_prompt_preview="", ide_source="", prefer=""
        )
    ]
    assert chunks == ["fallback chunk"]
    mock_auth.assert_called_once()
