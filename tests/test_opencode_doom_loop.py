"""Tests for opencode_doom_loop.py — doom loop detection and break."""

import json

import pytest

from opencode_doom_loop import (
    DOOM_LOOP_THRESHOLD,
    _extract_tool_call_key,
    build_doom_loop_warning,
    detect_doom_loop,
    inject_doom_loop_break,
)

# ── _extract_tool_call_key ────────────────────────────────────────────────────


class TestExtractToolCallKey:
    def test_basic(self):
        tc = {"function": {"name": "read_file", "arguments": '{"path": "x.txt"}'}}
        key = _extract_tool_call_key(tc)
        assert key is not None
        assert key.startswith("read_file:")

    def test_empty_name(self):
        tc = {"function": {"name": "", "arguments": "{}"}}
        assert _extract_tool_call_key(tc) is None

    def test_dict_arguments(self):
        tc = {"function": {"name": "read", "arguments": {"path": "x"}}}
        key = _extract_tool_call_key(tc)
        assert "read:" in key

    def test_sorted_arguments(self):
        tc1 = {"function": {"name": "f", "arguments": '{"b":1,"a":2}'}}
        tc2 = {"function": {"name": "f", "arguments": '{"a":2,"b":1}'}}
        assert _extract_tool_call_key(tc1) == _extract_tool_call_key(tc2)

    def test_malformed_arguments(self):
        tc = {"function": {"name": "f", "arguments": "not json"}}
        key = _extract_tool_call_key(tc)
        assert key is not None
        assert "_raw" in key


# ── detect_doom_loop ─────────────────────────────────────────────────────────


class TestDetectDoomLoop:
    def _make_assistant_with_tool(self, name, args="{}"):
        return {
            "role": "assistant",
            "tool_calls": [
                {"id": "c1", "function": {"name": name, "arguments": args}}
            ],
        }

    def _make_tool_result(self):
        return {"role": "tool", "content": "done", "tool_call_id": "c1"}

    def test_no_messages(self):
        assert detect_doom_loop([]) is None

    def test_single_call(self):
        msgs = [self._make_assistant_with_tool("read")]
        assert detect_doom_loop(msgs) is None

    def test_two_identical_calls_below_threshold(self):
        msgs = [
            self._make_assistant_with_tool("read"),
            self._make_tool_result(),
            self._make_assistant_with_tool("read"),
        ]
        # Default threshold=3, so 2 identical is not enough
        assert detect_doom_loop(msgs) is None

    def test_three_identical_calls_detected(self):
        msgs = [
            self._make_assistant_with_tool("read", '{"path":"x"}'),
            self._make_tool_result(),
            self._make_assistant_with_tool("read", '{"path":"x"}'),
            self._make_tool_result(),
            self._make_assistant_with_tool("read", '{"path":"x"}'),
        ]
        result = detect_doom_loop(msgs)
        assert result is not None
        assert result["tool_name"] == "read"
        assert result["count"] == 3

    def test_different_args_not_loop(self):
        msgs = [
            self._make_assistant_with_tool("read", '{"path":"a"}'),
            self._make_tool_result(),
            self._make_assistant_with_tool("read", '{"path":"b"}'),
            self._make_tool_result(),
            self._make_assistant_with_tool("read", '{"path":"c"}'),
        ]
        assert detect_doom_loop(msgs) is None

    def test_different_tools_not_loop(self):
        msgs = [
            self._make_assistant_with_tool("read"),
            self._make_tool_result(),
            self._make_assistant_with_tool("write"),
            self._make_tool_result(),
            self._make_assistant_with_tool("read"),
        ]
        assert detect_doom_loop(msgs) is None

    def test_user_message_breaks_chain(self):
        msgs = [
            self._make_assistant_with_tool("read"),
            self._make_tool_result(),
            self._make_assistant_with_tool("read"),
            self._make_tool_result(),
            {"role": "user", "content": "try something else"},
            self._make_assistant_with_tool("read"),
        ]
        # User message in between breaks the consecutive chain
        assert detect_doom_loop(msgs) is None

    def test_custom_threshold(self):
        msgs = [
            self._make_assistant_with_tool("f"),
            self._make_tool_result(),
            self._make_assistant_with_tool("f"),
        ]
        assert detect_doom_loop(msgs, threshold=2) is not None

    def test_no_tool_calls(self):
        msgs = [
            {"role": "assistant", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        assert detect_doom_loop(msgs) is None

    def test_threshold_below_2(self):
        msgs = [self._make_assistant_with_tool("f")]
        assert detect_doom_loop(msgs, threshold=1) is None


# ── build_doom_loop_warning ──────────────────────────────────────────────────


class TestBuildDoomLoopWarning:
    def test_warning_message(self):
        info = {"tool_name": "bash", "count": 5, "arguments": "{}"}
        warning = build_doom_loop_warning(info)
        assert "bash" in warning
        assert "5" in warning
        assert "WARNING" in warning

    def test_unknown_tool(self):
        info = {"tool_name": "unknown", "count": 3, "arguments": "{}"}
        warning = build_doom_loop_warning(info)
        assert "unknown" in warning


# ── inject_doom_loop_break ────────────────────────────────────────────────────


class TestInjectDoomLoopBreak:
    def test_appends_user_message(self):
        msgs = [{"role": "user", "content": "hi"}]
        info = {"tool_name": "bash", "count": 3, "arguments": "{}"}
        result = inject_doom_loop_break(msgs, info)
        assert len(result) == 2
        assert result[-1]["role"] == "user"

    def test_break_message_content(self):
        msgs = []
        info = {"tool_name": "read_file", "count": 5, "arguments": "{}"}
        result = inject_doom_loop_break(msgs, info)
        text = result[0]["content"][0]["text"]
        assert "read_file" in text
        assert "DIFFERENT" in text

    def test_original_not_mutated(self):
        msgs = [{"role": "user", "content": "hi"}]
        info = {"tool_name": "x", "count": 3, "arguments": "{}"}
        result = inject_doom_loop_break(msgs, info)
        assert len(msgs) == 1
        assert len(result) == 2


# ── DOOM_LOOP_THRESHOLD constant ──────────────────────────────────────────────


class TestConstants:
    def test_default_threshold(self):
        assert DOOM_LOOP_THRESHOLD == 3
