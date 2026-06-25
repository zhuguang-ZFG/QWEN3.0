"""Tests for routes/chat_handler_dispatch.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import JSONResponse, StreamingResponse

from chat_models import ChatRequest, Message
from routes import chat_handler_dispatch as dispatch
from routes.chat_handler_dispatch import ChatRunContext, RoutePrefs, resolve_route_prefs, start_chat_run


def _request(content: str = "hello", model: str = "lima", stream: bool = False) -> ChatRequest:
    return ChatRequest(model=model, messages=[Message(role="user", content=content)], stream=stream)


def make_ctx() -> ChatRunContext:
    return ChatRunContext(
        chat_id="chat-123",
        query="hello",
        t0=0.0,
        fmt="openai",
        request_model=None,
        client_ip="127.0.0.1",
        ide_source="",
        sys_prompt_preview="",
        memory_recall_meta={},
        memory_session_id=None,
        preflight=SimpleNamespace(
            request_messages=[{"role": "user", "content": "hello"}],
            prompt_context_messages=[{"role": "user", "content": "hello"}],
            system_prompt="",
            memory_recall_meta={},
            memory_session_id=None,
        ),
        prefs=RoutePrefs(prefer=None, ide_source="", use_thinking=False),
    )


def test_resolve_route_prefs_fast_model():
    req = _request(model="fast")
    prefs = resolve_route_prefs(req, "", "hello")
    assert prefs.prefer == "longcat_lite"


def test_resolve_route_prefs_expert_model():
    req = _request(model="expert")
    prefs = resolve_route_prefs(req, "", "hello")
    assert prefs.prefer == "scnet_ds_pro"
    assert req.thinking is True


def test_resolve_route_prefs_code_model():
    req = _request(model="code")
    prefs = resolve_route_prefs(req, "", "write code")
    assert prefs.prefer == "scnet_qwen235b"
    assert prefs.ide_source == "chat_code_mode"


def test_resolve_route_prefs_claude_ide():
    req = _request(model="other")
    prefs = resolve_route_prefs(req, "claude_code", "hello")
    assert prefs.prefer == "scnet_ds_pro"


@patch("routes.chat_handler_dispatch.routing_intent.detect_thinking_intent", return_value=True)
def test_resolve_route_prefs_detects_thinking_intent(mock_detect):
    req = _request()
    prefs = resolve_route_prefs(req, "", "think deeply")
    assert prefs.use_thinking is True
    mock_detect.assert_called_once_with("think deeply")


@patch("routes.chat_handler_dispatch.make_chat_id", return_value="chat-123")
@patch("routes.chat_handler_dispatch.time.time", return_value=1.0)
@patch("routes.chat_handler_dispatch.prepare_chat_preflight")
@patch("routes.chat_handler_dispatch.routing_intent.detect_thinking_intent", return_value=False)
def test_start_chat_run_builds_context(mock_thinking, mock_preflight, mock_time, mock_chat_id):
    mock_preflight.return_value = SimpleNamespace(
        request_messages=[{"role": "user", "content": "hi"}],
        prompt_context_messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
        memory_recall_meta={"checked": True},
        memory_session_id="sess-1",
    )
    req = _request("hi")
    ctx = start_chat_run(
        req,
        fmt="openai",
        request_model=None,
        client_ip="1.2.3.4",
        ide_source="test",
        sys_prompt_preview="preview",
        request_headers={},
        trace=None,
    )
    assert ctx.chat_id == "chat-123"
    assert ctx.query == "hi"
    assert ctx.fmt == "openai"
    assert ctx.client_ip == "1.2.3.4"
    assert ctx.memory_session_id == "sess-1"
    mock_preflight.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.routing_intent.detect_image_intent", return_value=(False, ""))
async def test_maybe_image_response_no_intent(mock_detect):
    result = await dispatch.maybe_image_response(
        make_ctx(),
        _request(),
        model_id="lima-test",
        record_request=MagicMock(),
        build_pollinations_url=lambda p, s: "url",
    )
    assert result is None


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.routing_intent.detect_image_intent", return_value=(True, "a cat"))
async def test_maybe_image_response_non_stream(mock_detect):
    ctx_obj = make_ctx()
    record_request = MagicMock()
    result = await dispatch.maybe_image_response(
        ctx_obj,
        _request(),
        model_id="lima-test",
        record_request=record_request,
        build_pollinations_url=lambda p, s: f"https://pollinations.ai/{p}?size={s}",
    )
    assert isinstance(result, JSONResponse)
    body = result.body.decode()
    assert "https://pollinations.ai/a cat?size=1024x1024" in body
    record_request.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.routing_intent.detect_image_intent", return_value=(True, "a cat"))
async def test_maybe_image_response_stream(mock_detect):
    ctx_obj = make_ctx()
    result = await dispatch.maybe_image_response(
        ctx_obj,
        _request(stream=True),
        model_id="lima-test",
        record_request=MagicMock(),
        build_pollinations_url=lambda p, s: "url",
    )
    assert isinstance(result, StreamingResponse)


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.thinking_route", new_callable=AsyncMock, return_value=None)
async def test_maybe_thinking_response_skips_when_disabled(mock_thinking):
    ctx_obj = make_ctx()
    ctx_obj.prefs.use_thinking = False
    result = await dispatch.maybe_thinking_response(
        ctx_obj, _request(), model_id="lima-test", record_request=MagicMock()
    )
    assert result is None


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.thinking_route", new_callable=AsyncMock)
async def test_maybe_thinking_response_non_stream(mock_thinking):
    mock_thinking.return_value = {"answer": "deep thought", "backend": "thinker"}
    ctx_obj = make_ctx()
    ctx_obj.prefs.use_thinking = True
    record_request = MagicMock()
    result = await dispatch.maybe_thinking_response(
        ctx_obj, _request(), model_id="lima-test", record_request=record_request
    )
    assert isinstance(result, JSONResponse)
    body = result.body.decode()
    assert "deep thought" in body
    assert "thinking_mode" in body
    record_request.assert_called_once()


@patch("routes.chat_handler_dispatch.routing_intent.analyze_intent", return_value={"intent": "chat"})
@patch("routes.chat_handler_dispatch.stream_response")
def test_build_streaming_response(mock_stream, mock_intent):
    async def _gen():
        yield "data: {}\n\n"

    mock_stream.return_value = _gen()
    ctx_obj = make_ctx()
    ctx_obj.prefs.prefer = "longcat_lite"
    result = dispatch.build_streaming_response(ctx_obj, _request(stream=True))
    assert isinstance(result, StreamingResponse)
    mock_stream.assert_called_once()
    args, kwargs = mock_stream.call_args
    assert args[0] == "chat-123"
    assert args[2] is False
    assert kwargs["prefer"] == "longcat_lite"


@pytest.mark.asyncio
@patch("routes.chat_handler_dispatch.routing_intent.analyze_intent", return_value={"intent": "chat"})
@patch("routes.chat_handler_dispatch.v3_route", return_value={"answer": "ok"})
async def test_execute_non_stream_route_v3(mock_v3, mock_intent):
    ctx_obj = make_ctx()
    req = _request()
    result, intent = await dispatch.execute_non_stream_route(ctx_obj, req)
    assert result["answer"] == "ok"
    assert intent == {"intent": "chat"}
    mock_v3.assert_called_once()
