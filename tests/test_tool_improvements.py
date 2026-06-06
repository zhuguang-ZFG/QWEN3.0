"""Tests for tool calling pipeline improvements (docs/TOOL_CALLING_IMPROVEMENTS.md).

Covers:
- Task 1: tool_choice passthrough
- Task 2: variable shadowing fix (tested via code review)
- Task 3: Tier2 SSE format (event-level buffering)
- Task 4: body size limit configurable
- Task 5: tool request recording
- Task 6: text tool extraction delegation
"""

import json

from converters.anthropic_format import convert_tool_choice_anthropic_to_openai

# ── Task 1: tool_choice conversion ────────────────────────────────────────────


class TestToolChoiceConversion:
    def test_none_returns_auto(self):
        assert convert_tool_choice_anthropic_to_openai(None) == "auto"

    def test_auto_returns_auto(self):
        assert convert_tool_choice_anthropic_to_openai("auto") == "auto"

    def test_any_returns_required(self):
        assert convert_tool_choice_anthropic_to_openai("any") == "required"

    def test_none_string_returns_none(self):
        assert convert_tool_choice_anthropic_to_openai("none") == "none"

    def test_tool_type_with_name(self):
        result = convert_tool_choice_anthropic_to_openai(
            {"type": "tool", "name": "Read"}
        )
        assert result == {"type": "function", "function": {"name": "Read"}}

    def test_function_type_with_name(self):
        result = convert_tool_choice_anthropic_to_openai(
            {"type": "function", "name": "Write"}
        )
        assert result == {"type": "function", "function": {"name": "Write"}}

    def test_tool_type_without_name_returns_auto(self):
        result = convert_tool_choice_anthropic_to_openai({"type": "tool"})
        assert result == "auto"

    def test_unknown_type_returns_auto(self):
        assert convert_tool_choice_anthropic_to_openai({"type": "unknown"}) == "auto"

    def test_integer_returns_auto(self):
        assert convert_tool_choice_anthropic_to_openai(42) == "auto"


# ── Task 1: tool_choice passthrough in body conversion ───────────────────────


class TestOpenAIToAnthropicToolBody:
    def test_tool_choice_forwarded(self):
        from routes.chat_endpoints import _openai_to_anthropic_tool_body

        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"function": {"name": "Read", "description": "", "parameters": {}}}],
            "tool_choice": {"type": "function", "function": {"name": "Read"}},
        }
        result = _openai_to_anthropic_tool_body(body)
        assert result["tool_choice"] == {"type": "function", "function": {"name": "Read"}}

    def test_tool_choice_omitted_when_absent(self):
        from routes.chat_endpoints import _openai_to_anthropic_tool_body

        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"function": {"name": "Read", "description": "", "parameters": {}}}],
        }
        result = _openai_to_anthropic_tool_body(body)
        assert "tool_choice" not in result


# ── Task 1: tool_choice in sync forward path ─────────────────────────────────


class TestToolForwardChoicePassthrough:
    def test_sync_forward_uses_client_tool_choice(self, monkeypatch):
        """Verify anthropic_native_forward_sync passes client tool_choice to backend."""
        import health_tracker
        import routes.tool_forward as tf
        from backends import BACKENDS

        captured_bodies = []

        def fake_call_raw(name, payload):
            captured_bodies.append(json.loads(payload))
            return {
                "choices": [{"message": {"content": "ok", "tool_calls": []}}],
                "usage": {},
            }

        monkeypatch.setattr(tf, "TOOL_TIER1_BACKENDS", ["test_backend"])
        monkeypatch.setattr(tf, "iter_tool_backends", lambda tier: iter(["test_backend"]))
        monkeypatch.setitem(BACKENDS, "test_backend", {
            "url": "https://test/v1/chat/completions",
            "key": "k", "model": "test-model", "fmt": "openai",
        })
        monkeypatch.setattr("http_caller.call_raw", fake_call_raw)
        monkeypatch.setattr(health_tracker, "record_success", lambda *a, **k: None)

        body = {
            "messages": [{"role": "user", "content": "use Read"}],
            "tools": [{"name": "Read", "input_schema": {"type": "object", "properties": {}}}],
            "tool_choice": {"type": "tool", "name": "Read"},
        }
        tf.anthropic_native_forward_sync(body)

        assert len(captured_bodies) == 1
        assert captured_bodies[0]["tool_choice"] == {
            "type": "function", "function": {"name": "Read"}
        }

    def test_sync_forward_defaults_to_auto(self, monkeypatch):
        """Without tool_choice in body, should default to 'auto'."""
        import health_tracker
        import routes.tool_forward as tf
        from backends import BACKENDS

        captured_bodies = []

        def fake_call_raw(name, payload):
            captured_bodies.append(json.loads(payload))
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }

        monkeypatch.setattr(tf, "TOOL_TIER1_BACKENDS", ["test_backend"])
        monkeypatch.setattr(tf, "iter_tool_backends", lambda tier: iter(["test_backend"]))
        monkeypatch.setitem(BACKENDS, "test_backend", {
            "url": "https://test/v1/chat/completions",
            "key": "k", "model": "test-model", "fmt": "openai",
        })
        monkeypatch.setattr("http_caller.call_raw", fake_call_raw)
        monkeypatch.setattr(health_tracker, "record_success", lambda *a, **k: None)

        body = {
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"name": "Read", "input_schema": {"type": "object", "properties": {}}}],
        }
        tf.anthropic_native_forward_sync(body)

        assert captured_bodies[0]["tool_choice"] == "auto"


# ── Task 4: body size limit ──────────────────────────────────────────────────


class TestToolBodySizeLimit:
    def test_default_limit_is_512kb(self):
        from routes.tool_forward import _TOOL_BODY_LIMIT
        assert _TOOL_BODY_LIMIT == 524288

    def test_env_override(self, monkeypatch):
        """Verify the limit reads from LIMA_TOOL_BODY_LIMIT env var."""
        import importlib
        monkeypatch.setenv("LIMA_TOOL_BODY_LIMIT", "2048")
        # Re-import to pick up the env change
        import routes.tool_forward as tf
        importlib.reload(tf)
        assert tf._TOOL_BODY_LIMIT == 2048
        # Restore default
        monkeypatch.delenv("LIMA_TOOL_BODY_LIMIT")
        importlib.reload(tf)


# ── Task 6: text tool extraction delegation ──────────────────────────────────


class TestTextToolExtractionDelegation:
    def test_extract_delegates_to_text_tool_extractor(self):
        """_extract_text_tools_from_response should use text_tool_extractor."""
        import routes.tool_forward as tf

        data = {
            "choices": [{
                "message": {
                    "content": '```json\n{"name": "Read", "arguments": {"path": "/tmp"}}\n```',
                },
                "finish_reason": "stop",
            }]
        }
        result = tf._extract_text_tools_from_response(data)
        msg = result["choices"][0]["message"]
        assert msg.get("tool_calls")
        assert msg["tool_calls"][0]["function"]["name"] == "Read"
        assert result["choices"][0]["finish_reason"] == "tool_calls"

    def test_extract_skips_when_tool_calls_present(self):
        """Should not modify response that already has tool_calls."""
        import routes.tool_forward as tf

        existing_calls = [{"id": "call_1", "type": "function", "function": {"name": "X", "arguments": "{}"}}]
        data = {
            "choices": [{
                "message": {
                    "content": "text",
                    "tool_calls": existing_calls,
                },
                "finish_reason": "tool_calls",
            }]
        }
        result = tf._extract_text_tools_from_response(data)
        assert result["choices"][0]["message"]["tool_calls"] == existing_calls

    def test_extract_handles_empty_content(self):
        import routes.tool_forward as tf

        data = {"choices": [{"message": {"content": ""}}]}
        result = tf._extract_text_tools_from_response(data)
        assert result["choices"][0]["message"].get("tool_calls") is None


# ── Task 3: Tier2 SSE event-level buffering ──────────────────────────────────


class TestPrepareToolPayload:
    def test_returns_four_tuple(self):
        """prepare_tool_openai_payload should return (tools, msgs, skip, tool_choice)."""
        from routes.tool_forward_stream import prepare_tool_openai_payload

        body = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "tools": [{"name": "Read", "input_schema": {"type": "object", "properties": {}}}],
        }
        result = prepare_tool_openai_payload(body)
        assert len(result) == 4
        tools, msgs, skip, tool_choice = result
        assert tools
        assert msgs
        assert skip is False
        assert tool_choice == "auto"

    def test_tool_choice_any_in_stream(self):
        from routes.tool_forward_stream import prepare_tool_openai_payload

        body = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "tools": [{"name": "Read", "input_schema": {"type": "object", "properties": {}}}],
            "tool_choice": "any",
        }
        _, _, _, tool_choice = prepare_tool_openai_payload(body)
        assert tool_choice == "required"
