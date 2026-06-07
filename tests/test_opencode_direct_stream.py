"""OpenCode direct stream fast path tests."""

from __future__ import annotations

from unittest.mock import patch

from http_errors import BackendError
from chat_models import ChatRequest, Message
from routes.chat_handler_dispatch import (
    ChatRunContext,
    RoutePrefs,
    build_streaming_response,
)
from routes.chat_preflight import ChatPreflightResult


def test_resolve_opencode_backend_prefers_healthy_prefer():
    from routes.opencode_direct_stream import resolve_opencode_backend

    with patch("routes.opencode_direct_stream.health_tracker") as ht, patch(
        "routes.opencode_direct_stream._select_key", return_value=("key", None)
    ), patch("routes.opencode_direct_stream.BACKENDS", {"scnet_ds_flash": {"url": "x"}}):
        ht.is_cooled_down.return_value = False
        assert resolve_opencode_backend("scnet_ds_flash") == "scnet_ds_flash"


def test_read_timeout_uses_opencode_floor():
    from routes.opencode_direct_stream import _read_timeout_for

    assert _read_timeout_for({}) >= 180


def test_read_timeout_preserves_larger_backend_timeout():
    from routes.opencode_direct_stream import _read_timeout_for

    assert _read_timeout_for({"timeout": 240}) == 240


async def test_stream_response_uses_prefer_without_speculative():

    from routes.chat_stream import stream_response

    chunks: list[str] = []

    async def _fake_real_stream(*_a, **_k):
        yield "hello"

    with patch(
        "routes.chat_stream.real_stream_chunks_async", side_effect=_fake_real_stream
    ) as real_stream, patch(
        "routes.chat_stream.speculative_stream_chunks"
    ) as speculative:
        async for item in stream_response(
            "chat-1",
            "hi",
            False,
            messages=[{"role": "user", "content": "hi"}],
            prefer="scnet_ds_flash",
            has_tools=False,
        ):
            chunks.append(item)
        real_stream.assert_called_once()
        speculative.assert_not_called()

    assert any("hello" in c for c in chunks)
    assert any("[DONE]" in c for c in chunks)


async def test_build_streaming_response_passes_opencode_headers_to_direct_stream(monkeypatch):
    import routes.chat_handler_dispatch as dispatch
    import routes.opencode_direct_stream as direct_stream

    captured: dict = {}

    async def fake_stream_openai_passthrough(**kwargs):
        captured.update(kwargs)
        yield 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'

    request_headers = {
        "user-agent": "opencode",
        "x-opencode-session": "session-123",
        "x-opencode-request": "request-456",
        "x-parent-session-id": "parent-789",
    }
    req = ChatRequest(
        model="lima-1.3",
        stream=True,
        messages=[Message(role="user", content="use a tool")],
        tools=[{
            "type": "function",
            "function": {
                "name": "read",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
    )
    ctx = ChatRunContext(
        chat_id="chat-headers",
        query="use a tool",
        t0=0.0,
        fmt="openai",
        request_model="lima-1.3",
        client_ip="127.0.0.1",
        user_agent="opencode",
        ide_source="opencode",
        sys_prompt_preview="",
        memory_recall_meta={},
        memory_session_id=None,
        preflight=ChatPreflightResult(
            request_messages=[{"role": "user", "content": "use a tool"}],
            prompt_context_messages=[{"role": "user", "content": "use a tool"}],
            system_prompt="",
            memory_recall_meta={},
            memory_session_id=None,
        ),
        prefs=RoutePrefs(prefer="scnet_ds_flash", ide_source="opencode", use_thinking=False),
        request_headers=request_headers,
    )

    monkeypatch.setattr(dispatch, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer: prefer)
    monkeypatch.setattr(
        direct_stream,
        "stream_openai_passthrough",
        fake_stream_openai_passthrough,
    )

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert captured["request_headers"] == request_headers
    assert any("ok" in chunk for chunk in chunks)


def _opencode_tool_context() -> tuple[ChatRunContext, ChatRequest]:
    req = ChatRequest(
        model="lima-1.3",
        stream=True,
        messages=[Message(role="user", content="use a tool")],
        tools=[{
            "type": "function",
            "function": {
                "name": "read",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
    )
    ctx = ChatRunContext(
        chat_id="chat-error-boundary",
        query="use a tool",
        t0=0.0,
        fmt="openai",
        request_model="lima-1.3",
        client_ip="127.0.0.1",
        user_agent="opencode",
        ide_source="opencode",
        sys_prompt_preview="",
        memory_recall_meta={},
        memory_session_id=None,
        preflight=ChatPreflightResult(
            request_messages=[{"role": "user", "content": "use a tool"}],
            prompt_context_messages=[{"role": "user", "content": "use a tool"}],
            system_prompt="",
            memory_recall_meta={},
            memory_session_id=None,
        ),
        prefs=RoutePrefs(prefer="scnet_ds_flash", ide_source="opencode", use_thinking=False),
        request_headers={"user-agent": "opencode"},
    )
    return ctx, req


async def test_direct_stream_backend_error_before_first_chunk_falls_back(monkeypatch):
    import routes.chat_handler_dispatch as dispatch
    import routes.opencode_direct_stream as direct_stream

    fallback_called = False

    async def failing_direct_stream(**_kwargs):
        raise BackendError("backend busy", status_code=503)
        yield ""

    async def fake_stream_response(*_args, **_kwargs):
        nonlocal fallback_called
        fallback_called = True
        yield 'data: {"choices":[{"delta":{"content":"fallback"}}]}\n\n'
        yield "data: [DONE]\n\n"

    ctx, req = _opencode_tool_context()
    monkeypatch.setattr(dispatch, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer: prefer)
    monkeypatch.setattr(direct_stream, "stream_openai_passthrough", failing_direct_stream)
    monkeypatch.setattr(dispatch, "stream_response", fake_stream_response)

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert fallback_called
    assert any("fallback" in chunk for chunk in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"


async def test_direct_stream_backend_error_after_first_chunk_emits_sse_error(monkeypatch):
    import routes.chat_handler_dispatch as dispatch
    import routes.opencode_direct_stream as direct_stream

    async def partially_failing_direct_stream(**_kwargs):
        yield 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        raise BackendError("backend rate limited", status_code=429)

    async def fake_stream_response(*_args, **_kwargs):
        raise AssertionError("fallback must not start after partial stream output")
        yield ""

    ctx, req = _opencode_tool_context()
    monkeypatch.setattr(dispatch, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer: prefer)
    monkeypatch.setattr(
        direct_stream,
        "stream_openai_passthrough",
        partially_failing_direct_stream,
    )
    monkeypatch.setattr(dispatch, "stream_response", fake_stream_response)

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert any("partial" in chunk for chunk in chunks)
    assert any('"type": "error"' in chunk for chunk in chunks)
    assert any("server_is_overloaded" in chunk for chunk in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"
