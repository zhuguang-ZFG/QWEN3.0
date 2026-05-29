"""Anthropic tool-route context preflight (CTX-003)."""

from converters.anthropic_format import (
    PREFLIGHT_MARKER,
    anthropic_system_text,
    convert_messages_anthropic_to_openai,
    inject_anthropic_body_preflight,
    inject_anthropic_context_preflight,
)


def _coding_body():
    return {
        "messages": [
            {
                "role": "user",
                "content": "Fix D:/GIT/server.py after SyntaxError: invalid syntax",
            }
        ],
        "system": "Working directory: D:/GIT",
        "tools": [{"name": "Read", "input_schema": {"type": "object"}}],
    }


def test_inject_anthropic_context_preflight_openai_messages():
    body = _coding_body()
    openai_msgs = convert_messages_anthropic_to_openai(body["messages"])
    inject_anthropic_context_preflight(openai_msgs, body)

    assert openai_msgs[0]["role"] == "system"
    assert PREFLIGHT_MARKER in openai_msgs[0]["content"]
    assert "server.py" in openai_msgs[0]["content"]


def test_inject_anthropic_body_preflight_string_system():
    body = _coding_body()
    openai_msgs = convert_messages_anthropic_to_openai(body["messages"])
    inject_anthropic_body_preflight(body, openai_msgs)

    system = anthropic_system_text(body)
    assert PREFLIGHT_MARKER in system
    assert "Working directory" in system


def test_inject_anthropic_body_preflight_block_system():
    body = _coding_body()
    body["system"] = [{"type": "text", "text": "Claude Code agent"}]
    openai_msgs = convert_messages_anthropic_to_openai(body["messages"])
    inject_anthropic_body_preflight(body, openai_msgs)

    assert PREFLIGHT_MARKER in anthropic_system_text(body)
    assert body["system"][0]["type"] == "text"


def test_preflight_is_idempotent_on_body():
    body = _coding_body()
    openai_msgs = convert_messages_anthropic_to_openai(body["messages"])
    inject_anthropic_body_preflight(body, openai_msgs)
    first = anthropic_system_text(body)
    inject_anthropic_body_preflight(body, openai_msgs)
    assert anthropic_system_text(body) == first


def test_tier2_forward_includes_body_preflight(monkeypatch):
    import routes.tool_forward as tool_forward

    captured: dict = {}

    body = _coding_body()

    class _Resp:
        def read(self):
            return b'{"type":"message","role":"assistant","content":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=60):
        captured["payload"] = req.data.decode("utf-8")
        return _Resp()

    monkeypatch.setattr(tool_forward, "TOOL_TIER1_BACKENDS", [])
    monkeypatch.setattr(tool_forward, "ANTHROPIC_NATIVE_BACKENDS", ["longcat_chat"])
    monkeypatch.setattr(tool_forward, "pick_tool_backend", lambda tier: "longcat_chat")
    monkeypatch.setattr(tool_forward, "iter_tool_backends", lambda tier: iter(["longcat_chat"]))

    import health_tracker
    from backends import BACKENDS

    monkeypatch.setitem(
        BACKENDS,
        "longcat_chat",
        {
            "url": "https://example.test/v1/messages",
            "key": "k",
            "model": "LongCat",
            "fmt": "anthropic",
            "auth": "bearer",
        },
    )
    monkeypatch.setattr(health_tracker, "record_success", lambda *a, **k: None)
    monkeypatch.setattr(health_tracker, "record_failure", lambda *a, **k: None)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    tool_forward.anthropic_native_forward_sync(body)

    assert PREFLIGHT_MARKER in captured["payload"]
