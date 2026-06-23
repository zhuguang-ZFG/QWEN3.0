"""Tests for routes/chat_handler.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from chat_models import ChatRequest, Message
from routes import chat_handler


@pytest.fixture(autouse=True)
def _reset_handler():
    chat_handler._injected = False
    chat_handler._model_id = "lima-default"
    chat_handler._record_request = chat_handler._unconfigured_record_request
    chat_handler._record_fallback = chat_handler._unconfigured_record_fallback
    chat_handler._build_pollinations_url = None
    yield
    chat_handler._injected = False
    chat_handler._model_id = "lima-default"
    chat_handler._record_request = chat_handler._unconfigured_record_request
    chat_handler._record_fallback = chat_handler._unconfigured_record_fallback
    chat_handler._build_pollinations_url = None


@pytest.fixture
def injected_handler():
    chat_handler.inject_deps(
        model_id="lima-test",
        record_request=MagicMock(),
        record_fallback=MagicMock(),
        build_pollinations_url=lambda prompt, size: f"https://pollinations.ai/{prompt}?size={size}",
    )


def _request(content: str = "hello", stream: bool = False) -> ChatRequest:
    return ChatRequest(messages=[Message(role="user", content=content)], stream=stream)


@pytest.mark.asyncio
async def test_empty_query_raises_400():
    req = ChatRequest(messages=[Message(role="user", content="  ")])
    with pytest.raises(HTTPException) as exc_info:
        await chat_handler.handle_chat(req)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@patch("routes.chat_handler._start_trace", return_value=None)
@patch("routes.chat_handler.start_chat_run")
@patch("routes.chat_handler.maybe_image_response", new_callable=AsyncMock)
@patch("routes.chat_handler.maybe_thinking_response", new_callable=AsyncMock, return_value=None)
async def test_early_image_response(mock_thinking, mock_image, mock_start, mock_trace, injected_handler):
    image_resp = JSONResponse({"answer": "image-ok"})
    mock_image.return_value = image_resp
    mock_start.return_value = MagicMock()

    result = await chat_handler.handle_chat(_request("draw a cat"))

    assert result is image_resp
    mock_image.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_handler._start_trace", return_value=None)
@patch("routes.chat_handler.start_chat_run")
@patch("routes.chat_handler.maybe_image_response", new_callable=AsyncMock, return_value=None)
@patch("routes.chat_handler.maybe_thinking_response", new_callable=AsyncMock)
async def test_early_thinking_response(mock_thinking, mock_image, mock_start, mock_trace, injected_handler):
    thinking_resp = JSONResponse({"answer": "thinking-ok"})
    mock_thinking.return_value = thinking_resp
    mock_start.return_value = MagicMock()

    result = await chat_handler.handle_chat(_request("explain step by step"))

    assert result is thinking_resp
    mock_thinking.assert_called_once()


@pytest.mark.asyncio
@patch("routes.chat_handler._start_trace", return_value=None)
@patch("routes.chat_handler.start_chat_run")
@patch("routes.chat_handler.maybe_image_response", return_value=None)
@patch("routes.chat_handler.maybe_thinking_response", return_value=None)
@patch("routes.chat_handler.build_streaming_response", new_callable=MagicMock)
async def test_streaming_path(mock_stream, mock_thinking, mock_image, mock_start, mock_trace, injected_handler):
    ctx = MagicMock()
    ctx.query = "hello"
    mock_start.return_value = ctx
    stream_resp = StreamingResponse(("data: {}\n\n" for _ in range(1)), media_type="text/event-stream")
    mock_stream.return_value = stream_resp

    result = await chat_handler.handle_chat(_request("hello", stream=True))

    assert result is stream_resp
    mock_stream.assert_called_once_with(ctx, _request("hello", stream=True))


@pytest.mark.asyncio
@patch("routes.chat_handler._start_trace", return_value=None)
@patch("routes.chat_handler.start_chat_run")
@patch("routes.chat_handler.maybe_image_response", return_value=None)
@patch("routes.chat_handler.maybe_thinking_response", return_value=None)
@patch("routes.chat_handler.execute_non_stream_route")
@patch("routes.chat_handler.finalize_success_response")
async def test_non_stream_success(
    mock_finalize, mock_execute, mock_thinking, mock_image, mock_start, mock_trace, injected_handler
):
    ctx = MagicMock()
    ctx.query = "hello"
    mock_start.return_value = ctx
    mock_execute.return_value = ({"answer": "ok"}, {"intent": "chat"})
    final_resp = JSONResponse({"answer": "ok"})
    mock_finalize.return_value = final_resp

    result = await chat_handler.handle_chat(_request("hello"))

    assert result is final_resp
    mock_execute.assert_called_once_with(ctx, _request("hello"))
    mock_finalize.assert_called_once()
    _, kwargs = mock_finalize.call_args
    assert kwargs["model_id"] == "lima-test"


@pytest.mark.asyncio
@patch("routes.chat_handler._start_trace", return_value=None)
@patch("routes.chat_handler.start_chat_run")
@patch("routes.chat_handler.maybe_image_response", new_callable=AsyncMock, return_value=None)
@patch("routes.chat_handler.maybe_thinking_response", new_callable=AsyncMock, return_value=None)
@patch("routes.chat_handler.execute_non_stream_route")
@patch("routes.chat_handler.finalize_success_response", new_callable=AsyncMock)
async def test_trace_passed_to_start_chat_run(
    mock_finalize, mock_execute, mock_thinking, mock_image, mock_start, mock_trace, injected_handler
):
    trace = MagicMock()
    mock_trace.return_value = trace
    ctx = MagicMock()
    ctx.query = "hello"
    mock_start.return_value = ctx
    mock_execute.return_value = ({"answer": "ok"}, {"intent": "chat"})
    mock_finalize.return_value = JSONResponse({"answer": "ok"})

    await chat_handler.handle_chat(_request("hello"))

    _, kwargs = mock_start.call_args
    assert kwargs["trace"] is trace
