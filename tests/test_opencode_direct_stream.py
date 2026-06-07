"""OpenCode direct stream fast path tests."""

from __future__ import annotations

from unittest.mock import patch

from chat_models import ChatRequest, Message
from http_errors import BackendError
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


def test_meaningful_delta_detection_ignores_done():
    from routes.opencode_direct_stream import _has_meaningful_delta

    assert not _has_meaningful_delta("data: [DONE]")
    assert _has_meaningful_delta('data: {"choices":[{"delta":{"content":"ok"}}]}')


def test_resolve_opencode_backend_skips_non_tool_prefer_when_tools_required():
    from routes.opencode_direct_stream import resolve_opencode_backend

    backends = {
        "nvidia_qwen_coder": {"url": "x", "fmt": "openai"},
        "cfai_qwen_coder": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
        "scnet_ds_flash": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
    }
    with patch("routes.opencode_direct_stream.health_tracker") as ht, patch(
        "routes.opencode_direct_stream._select_key", return_value=("key", None)
    ), patch("routes.opencode_direct_stream.BACKENDS", backends):
        ht.is_cooled_down.return_value = False
        assert (
            resolve_opencode_backend("nvidia_qwen_coder", require_tools=True)
            == "scnet_ds_flash"
        )


def test_resolve_opencode_backend_prefers_stable_tool_backend_over_generic():
    from routes.opencode_direct_stream import resolve_opencode_backend

    backends = {
        "nvidia_qwen_coder": {"url": "x", "fmt": "openai"},
        "cfai_qwen_coder": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
        "scnet_ds_pro": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
    }
    with patch("routes.opencode_direct_stream.health_tracker") as ht, patch(
        "routes.opencode_direct_stream._select_key", return_value=("key", None)
    ), patch("routes.opencode_direct_stream.BACKENDS", backends):
        ht.is_cooled_down.return_value = False
        assert (
            resolve_opencode_backend("nvidia_qwen_coder", require_tools=True)
            == "scnet_ds_pro"
        )


def test_resolve_opencode_backend_preserves_explicit_stable_tool_prefer():
    from routes.opencode_direct_stream import resolve_opencode_backend

    backends = {
        "scnet_ds_flash": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
        "scnet_ds_pro": {"url": "x", "fmt": "openai", "caps": ["tool_calls"]},
    }
    with patch("routes.opencode_direct_stream.health_tracker") as ht, patch(
        "routes.opencode_direct_stream._select_key", return_value=("key", None)
    ), patch("routes.opencode_direct_stream.BACKENDS", backends):
        ht.is_cooled_down.return_value = False
        assert (
            resolve_opencode_backend("scnet_ds_flash", require_tools=True)
            == "scnet_ds_flash"
        )


def test_backend_upload_limit_text_is_treated_as_backend_error():
    from routes.opencode_direct_stream import _ensure_not_backend_error_text

    try:
        _ensure_not_backend_error_text(
            "cfai_qwen_coder",
            "抱歉，文件上传最大限制长度五万，请缩减后再试试吧",
        )
    except BackendError as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("upload-limit text should raise BackendError")


def _sample_read_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a workspace file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }


def test_text_tool_payload_plain_text_drops_native_tools_without_prompt():
    from opencode_text_tool_payload import prepare_opencode_text_tool_payload

    messages = [{"role": "user", "content": "Reply exactly OK. Do not use tools."}]
    adapted, native_tools, injected = prepare_opencode_text_tool_payload(
        "scnet_ds_pro", messages, [_sample_read_tool()], "auto"
    )

    assert adapted == messages
    assert native_tools is None
    assert injected is False


def test_text_tool_payload_injects_prompt_for_file_intent():
    from opencode_text_tool_payload import prepare_opencode_text_tool_payload

    adapted, native_tools, injected = prepare_opencode_text_tool_payload(
        "scnet_ds_pro",
        [{"role": "user", "content": "Read README.md and summarize it."}],
        [_sample_read_tool()],
        "auto",
    )

    assert native_tools is None
    assert injected is True
    assert adapted[0]["role"] == "system"
    assert "Available tools" in adapted[0]["content"]


def test_text_tool_payload_injects_prompt_for_forced_tool_choice():
    from opencode_text_tool_payload import prepare_opencode_text_tool_payload

    adapted, native_tools, injected = prepare_opencode_text_tool_payload(
        "scnet_ds_pro",
        [{"role": "user", "content": "Reply exactly OK."}],
        [_sample_read_tool()],
        {"type": "function", "function": {"name": "read"}},
    )

    assert native_tools is None
    assert injected is True
    assert adapted[0]["role"] == "system"


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
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer, **_kwargs: prefer)
    monkeypatch.setattr(
        direct_stream,
        "stream_openai_passthrough",
        fake_stream_openai_passthrough,
    )

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert captured["request_headers"] == request_headers
    assert any("ok" in chunk for chunk in chunks)


async def test_build_streaming_response_uses_direct_stream_without_tools(monkeypatch):
    import routes.chat_handler_dispatch as dispatch
    import routes.opencode_direct_stream as direct_stream

    captured: dict = {}

    async def fake_stream_openai_passthrough(**kwargs):
        captured.update(kwargs)
        yield 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'

    req = ChatRequest(
        model="lima-1.3",
        stream=True,
        messages=[Message(role="user", content="hello")],
    )
    ctx = ChatRunContext(
        chat_id="chat-no-tools",
        query="hello",
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
            request_messages=[{"role": "user", "content": "hello"}],
            prompt_context_messages=[{"role": "user", "content": "hello"}],
            system_prompt="",
            memory_recall_meta={},
            memory_session_id=None,
        ),
        prefs=RoutePrefs(prefer="scnet_ds_pro", ide_source="opencode", use_thinking=False),
        request_headers={"user-agent": "opencode"},
    )

    monkeypatch.setattr(dispatch, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer, **_kwargs: prefer)
    monkeypatch.setattr(
        direct_stream,
        "stream_openai_passthrough",
        fake_stream_openai_passthrough,
    )

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert captured["tools"] is None
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
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer, **_kwargs: prefer)
    monkeypatch.setattr(direct_stream, "stream_openai_passthrough", failing_direct_stream)
    monkeypatch.setattr(dispatch, "stream_response", fake_stream_response)

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]

    assert fallback_called
    assert any("fallback" in chunk for chunk in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"


async def test_direct_stream_synthesizes_explicit_tool_call(monkeypatch):
    import routes.chat_handler_dispatch as dispatch
    import routes.opencode_direct_stream as direct_stream

    ctx, req = _opencode_tool_context()
    req.messages = [Message(role="user", content="Call read for README.md")]
    req.tools = [{
        "type": "function",
        "function": {
            "name": "read",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }]
    ctx.query = "Call read for README.md"

    async def should_not_stream(**_kwargs):
        raise AssertionError("backend should not be called for explicit synthetic tool request")
        yield ""

    monkeypatch.setattr(dispatch, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer, **_kwargs: prefer)
    monkeypatch.setattr(direct_stream, "stream_openai_passthrough", should_not_stream)

    response = build_streaming_response(ctx, req)
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunks)

    assert '"tool_calls"' in body
    assert '"name": "read"' in body
    assert '\\"path\\": \\"README.md\\"' in body
    assert '"finish_reason": "tool_calls"' in body
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
    monkeypatch.setattr(direct_stream, "resolve_opencode_backend", lambda prefer, **_kwargs: prefer)
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


async def test_non_stream_direct_backend_error_falls_back(monkeypatch):
    import routes.chat_non_stream as chat_non_stream

    class FakeHandler:
        @staticmethod
        def needs_orchestration(*_args, **_kwargs):
            return False

        @staticmethod
        def v3_route(*_args, **_kwargs):
            return {"answer": "fallback answer", "backend": "fallback_backend"}

    ctx, req = _opencode_tool_context()
    req.stream = False

    def failing_call_api(*_args, **_kwargs):
        raise BackendError("preferred backend forbidden", status_code=403)

    monkeypatch.setattr(chat_non_stream, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(chat_non_stream, "_chat_handler", lambda: FakeHandler)
    monkeypatch.setattr(
        "routes.opencode_direct_stream.resolve_opencode_backend",
        lambda prefer, **_kwargs: prefer,
    )
    monkeypatch.setattr("http_caller.call_api", failing_call_api)

    result, _intent = await chat_non_stream.execute_non_stream_route(ctx, req)

    assert result["answer"] == "fallback answer"
    assert result["backend"] == "fallback_backend"


async def test_non_stream_text_tool_backend_does_not_forward_native_tools(monkeypatch):
    import routes.chat_non_stream as chat_non_stream

    class FakeHandler:
        @staticmethod
        def needs_orchestration(*_args, **_kwargs):
            return False

    captured: dict = {}
    ctx, req = _opencode_tool_context()
    req.stream = False
    req.messages = [Message(role="user", content="Read README.md")]
    ctx.query = "Read README.md"
    ctx.preflight.prompt_context_messages = [{"role": "user", "content": "Read README.md"}]
    ctx.preflight.request_messages = [{"role": "user", "content": "Read README.md"}]

    def fake_call_api(*args, **kwargs):
        captured["backend"] = args[0]
        captured["messages"] = args[1]
        captured["tools"] = kwargs.get("tools")
        return "OK"

    monkeypatch.setattr(chat_non_stream, "OPENCODE_DIRECT_STREAM", True)
    monkeypatch.setattr(chat_non_stream, "_chat_handler", lambda: FakeHandler)
    monkeypatch.setattr(
        "routes.opencode_direct_stream.resolve_opencode_backend",
        lambda _prefer, **_kwargs: "scnet_ds_pro",
    )
    monkeypatch.setattr("http_caller.call_api", fake_call_api)
    monkeypatch.setattr("http_caller.get_last_usage", lambda _backend: {})

    result, _intent = await chat_non_stream.execute_non_stream_route(ctx, req)

    assert result["answer"] == "OK"
    assert captured["backend"] == "scnet_ds_pro"
    assert captured["tools"] is None
    assert captured["messages"][0]["role"] == "system"
    assert "Available tools" in captured["messages"][0]["content"]
