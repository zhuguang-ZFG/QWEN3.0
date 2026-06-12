import asyncio
import json
import os
import tempfile

os.environ["LIMA_SESSION_DB"] = tempfile.mktemp(suffix=".db")
os.environ["LIMA_SESSION_MEMORY"] = "1"

from session_memory.processor import _session_id_from_headers
from session_memory.store import save_memory


class FakeTrace:
    def __init__(self):
        self.spans = []

    def start_span(self, name, **metadata):
        span = {"name": name, "metadata": metadata}
        self.spans.append(span)
        return span

    def end_span(self, span=None):
        if span is not None:
            span["ended"] = True


def test_server_context_builds_prompt_messages_without_memory(monkeypatch):
    import server_context

    monkeypatch.setitem(os.environ, "LIMA_SESSION_MEMORY", "0")
    req = type(
        "Req",
        (),
        {"messages": [{"role": "user", "content": "hello context"}]},
    )()

    result = server_context.build_prompt_context(req, system_prompt="base prompt")

    assert result.system_prompt == "base prompt"
    assert result.request_messages == [{"role": "user", "content": "hello context"}]
    assert result.prompt_context_messages[0] == {"role": "system", "content": "base prompt"}
    assert result.memory_recall_meta == {
        "checked": True,
        "applied": False,
        "prompt_chars_added": 0,
        "recalled_memory_ids": [],
    }


def test_apply_prompt_memory_recall_injects_memory_and_trace():
    from session_memory.prompt_recall import apply_prompt_memory_recall

    headers = {"x-forwarded-for": "10.9.0.1", "user-agent": "cursor"}
    sid = _session_id_from_headers(headers)
    save_memory(sid, "exchange", "remember routing_engine.py fallback bug")

    trace = FakeTrace()
    result = apply_prompt_memory_recall(
        [{"role": "user", "content": "routing bug again"}],
        system_prompt="base prompt",
        headers=headers,
        trace=trace,
    )

    assert result.applied is True
    assert "base prompt" in result.system_prompt
    assert "routing_engine.py" in result.system_prompt
    assert result.prompt_chars_added > 0
    assert trace.spans[0]["name"] == "prompt_memory_recall"
    assert trace.spans[0]["metadata"]["applied"] is True
    assert "routing_engine.py" not in json.dumps(trace.spans[0], ensure_ascii=False)


def test_handle_chat_applies_prompt_memory_before_routing(monkeypatch):
    import routes.chat_handler as chat_handler
    import router_classifier
    import server
    from chat_models import ChatRequest, Message

    headers = {"x-forwarded-for": "10.9.0.2", "user-agent": "cursor"}
    sid = _session_id_from_headers(headers)
    save_memory(sid, "exchange", "remember pytest routing fix")

    captured = {}

    def fake_analyze(query, system_prompt="", ide=""):
        captured["analyze_prompt"] = system_prompt
        return {"intent": "chat", "complexity": 0.1}

    def fake_v3_route(query, messages, system_prompt="", ide="", max_tokens=4096, **kwargs):
        captured["route_prompt"] = system_prompt
        return {"answer": "ok", "backend": "fake_backend", "total_ms": 1}

    monkeypatch.setenv("LIMA_SESSION_MEMORY", "1")
    monkeypatch.setattr(server.smart_router, "detect_image_intent", lambda query: (False, ""))
    monkeypatch.setattr(server.smart_router, "detect_thinking_intent", lambda query: False)
    monkeypatch.setattr(router_classifier, "analyze", fake_analyze)
    monkeypatch.setattr(chat_handler, "needs_orchestration", lambda query, intent: False)
    monkeypatch.setattr(chat_handler, "v3_route", fake_v3_route)
    monkeypatch.setattr(chat_handler, "_record_request", lambda *args, **kwargs: None)

    req = ChatRequest(
        messages=[Message(role="user", content="routing fix again")],
        max_tokens=128,
    )
    response = asyncio.run(
        server._handle_chat(
            req,
            fmt="openai",
            client_ip="10.9.0.2",
            ide_source="cursor",
            sys_prompt_preview="base prompt",
            request_headers=headers,
        )
    )
    data = json.loads(response.body.decode("utf-8"))

    assert "pytest routing fix" in captured["analyze_prompt"]
    assert "pytest routing fix" in captured["route_prompt"]
    assert data["x_lima_meta"]["memory_recall"]["applied"] is True


def test_handle_chat_writes_and_recalls_same_header_session(monkeypatch):
    import routes.chat_handler as chat_handler
    import router_classifier
    import server
    from chat_models import ChatRequest, Message

    headers = {"x-forwarded-for": "10.9.0.3", "user-agent": "cursor"}
    captured_prompts = []
    answers = iter(["we fixed banana cache", "ok"])

    def fake_analyze(query, system_prompt="", ide=""):
        captured_prompts.append(system_prompt)
        return {"intent": "chat", "complexity": 0.1}

    def fake_v3_route(query, messages, system_prompt="", ide="", max_tokens=4096, **kwargs):
        return {
            "answer": next(answers),
            "backend": "fake_backend",
            "total_ms": 1,
        }

    monkeypatch.setenv("LIMA_SESSION_MEMORY", "1")
    monkeypatch.setattr(server.smart_router, "detect_image_intent", lambda query: (False, ""))
    monkeypatch.setattr(server.smart_router, "detect_thinking_intent", lambda query: False)
    monkeypatch.setattr(router_classifier, "analyze", fake_analyze)
    monkeypatch.setattr(chat_handler, "needs_orchestration", lambda query, intent: False)
    monkeypatch.setattr(chat_handler, "v3_route", fake_v3_route)
    monkeypatch.setattr(chat_handler, "_record_request", lambda *args, **kwargs: None)

    first = ChatRequest(
        messages=[Message(role="user", content="please remember banana cache")],
        max_tokens=128,
    )
    second = ChatRequest(
        messages=[Message(role="user", content="what did we discuss?")],
        max_tokens=128,
    )

    asyncio.run(
        server._handle_chat(
            first,
            fmt="openai",
            client_ip="10.9.0.3",
            ide_source="cursor",
            request_headers=headers,
        )
    )
    asyncio.run(
        server._handle_chat(
            second,
            fmt="openai",
            client_ip="10.9.0.3",
            ide_source="cursor",
            request_headers=headers,
        )
    )

    assert "banana cache" in captured_prompts[-1]
