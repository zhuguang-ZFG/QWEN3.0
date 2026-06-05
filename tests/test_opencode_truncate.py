"""Tests for opencode_truncate.py — tool output truncation."""

import pytest
from opencode_truncate import (
    MAX_BYTES,
    MAX_LINES,
    truncate_output,
    truncate_tool_results_in_messages,
)


class TestTruncateOutput:
    """truncate_output() basic tests."""

    def test_short_text_unchanged(self):
        text = "hello\nworld"
        result, was_truncated = truncate_output(text)
        assert result == text
        assert was_truncated is False

    def test_empty_text(self):
        result, was_truncated = truncate_output("")
        assert result == ""
        assert was_truncated is False

    def test_line_limit_head(self):
        lines = [f"line {i}" for i in range(3000)]
        text = "\n".join(lines)
        result, was_truncated = truncate_output(text, max_lines=100)
        assert was_truncated is True
        assert "truncated" in result.lower()
        # Should contain first 100 lines
        assert "line 0" in result
        assert "line 99" in result
        # Should NOT contain line 2000+
        assert "line 2999" not in result

    def test_line_limit_tail(self):
        lines = [f"line {i}" for i in range(3000)]
        text = "\n".join(lines)
        result, was_truncated = truncate_output(text, max_lines=100, direction="tail")
        assert was_truncated is True
        assert "line 2999" in result
        assert "line 2900" in result
        assert "line 0" not in result

    def test_byte_limit(self):
        text = "x" * (MAX_BYTES + 10000)
        result, was_truncated = truncate_output(text, max_bytes=1000)
        assert was_truncated is True
        assert len(result.encode("utf-8")) < 2000  # 1000 bytes + hint

    def test_hints_contain_stats(self):
        text = "\n".join([f"line {i}" for i in range(5000)])
        result, was_truncated = truncate_output(text, max_lines=100)
        assert was_truncated
        assert "5000 lines" in result
        assert "100 lines" in result.lower() or "Showing 100" in result

    def test_exact_limit_not_truncated(self):
        text = "\n".join([f"l{i}" for i in range(100)])
        result, was_truncated = truncate_output(text, max_lines=100)
        assert was_truncated is False


class TestTruncateToolResultsInMessages:
    """truncate_tool_results_in_messages() integration tests."""

    def test_openai_tool_role(self):
        big_content = "x\n" * 3000
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "tool", "content": big_content, "tool_call_id": "tc1"},
        ]
        result = truncate_tool_results_in_messages(messages, max_lines=100)
        assert len(result) == 2
        assert result[0]["content"] == "hello"
        assert "truncated" in result[1]["content"].lower()

    def test_anthropic_tool_result(self):
        big_content = "y\n" * 3000
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": big_content, "tool_use_id": "tu1"},
                ],
            },
        ]
        result = truncate_tool_results_in_messages(messages, max_lines=100)
        block = result[0]["content"][0]
        assert "truncated" in block["content"].lower()

    def test_normal_messages_untouched(self):
        messages = [
            {"role": "user", "content": "small text"},
            {"role": "assistant", "content": "reply"},
        ]
        result = truncate_tool_results_in_messages(messages)
        assert result[0]["content"] == "small text"
        assert result[1]["content"] == "reply"

    def test_small_tool_result_untouched(self):
        messages = [
            {"role": "tool", "content": "ok", "tool_call_id": "tc1"},
        ]
        result = truncate_tool_results_in_messages(messages)
        assert result[0]["content"] == "ok"

    def test_preserves_message_order(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "x\n" * 3000, "tool_call_id": "tc1"},
            {"role": "assistant", "content": "done"},
        ]
        result = truncate_tool_results_in_messages(messages, max_lines=100)
        assert [m["role"] for m in result] == ["system", "user", "tool", "assistant"]

    def test_anthropic_nested_text_blocks(self):
        big = "z\n" * 3000
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu1",
                        "content": [{"type": "text", "text": big}],
                    },
                ],
            },
        ]
        result = truncate_tool_results_in_messages(messages, max_lines=100)
        inner = result[0]["content"][0]["content"]
        assert isinstance(inner, list)
        assert "truncated" in inner[0]["text"].lower()
