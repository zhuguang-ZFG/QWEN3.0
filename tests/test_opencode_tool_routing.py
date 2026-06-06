"""Tests for opencode_tool_routing.py — tool routing + Copilot _noop."""

import pytest
from opencode_tool_routing import (
    should_use_apply_patch,
    filter_tools_for_model,
    inject_noop_tool_if_needed,
    _has_tool_calls_in_history,
)


# ── Helper tool definitions ──

def _tool(name, desc="test"):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {}}}


class TestShouldUseApplyPatch:
    """should_use_apply_patch() tests."""

    def test_gpt5(self):
        assert should_use_apply_patch("gpt-5") is True

    def test_gpt5_turbo(self):
        assert should_use_apply_patch("gpt-5-turbo") is True

    def test_gpt5_mini(self):
        assert should_use_apply_patch("gpt-5-mini") is True

    def test_gpt_5(self):
        assert should_use_apply_patch("gpt_5") is True

    def test_gpt4(self):
        assert should_use_apply_patch("gpt-4o") is False

    def test_gpt4_turbo(self):
        assert should_use_apply_patch("gpt-4-turbo") is False

    def test_gpt_oss(self):
        assert should_use_apply_patch("gpt-oss-120b") is False

    def test_gptoss(self):
        assert should_use_apply_patch("gptoss_120b") is False

    def test_claude(self):
        assert should_use_apply_patch("claude-sonnet-4") is False

    def test_gemini(self):
        assert should_use_apply_patch("gemini-2.5-flash") is False

    def test_deepseek(self):
        assert should_use_apply_patch("deepseek-v3") is False

    def test_empty(self):
        assert should_use_apply_patch("") is False

    def test_none(self):
        assert should_use_apply_patch(None) is False


class TestFilterToolsForModel:
    """filter_tools_for_model() tests."""

    def test_gpt5_removes_edit_write(self):
        tools = [_tool("edit"), _tool("write"), _tool("apply_patch"), _tool("read")]
        result = filter_tools_for_model(tools, "gpt-5")
        names = {t["function"]["name"] for t in result}
        assert "edit" not in names
        assert "write" not in names
        assert "apply_patch" in names
        assert "read" in names

    def test_gpt4_keeps_edit_write(self):
        tools = [_tool("edit"), _tool("write"), _tool("apply_patch"), _tool("read")]
        result = filter_tools_for_model(tools, "gpt-4o")
        names = {t["function"]["name"] for t in result}
        assert "edit" in names
        assert "write" in names
        assert "apply_patch" not in names
        assert "read" in names

    def test_claude_keeps_all(self):
        tools = [_tool("edit"), _tool("write"), _tool("read")]
        result = filter_tools_for_model(tools, "claude-sonnet-4")
        assert len(result) == 3

    def test_empty_tools(self):
        assert filter_tools_for_model([], "gpt-5") == []

    def test_none_tools(self):
        assert filter_tools_for_model(None, "gpt-5") is None

    def test_no_matching_tools(self):
        tools = [_tool("read"), _tool("search")]
        result = filter_tools_for_model(tools, "gpt-5")
        assert len(result) == 2


class TestInjectNoopTool:
    """inject_noop_tool_if_needed() tests."""

    def test_copilot_no_tools_with_history(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"id": "tc1"}]},
        ]
        result = inject_noop_tool_if_needed(None, messages, "github_copilot")
        assert result is not None
        assert len(result) == 1
        assert result[0]["function"]["name"] == "_noop"

    def test_copilot_with_tools_no_inject(self):
        tools = [_tool("edit")]
        messages = [{"role": "assistant", "tool_calls": [{"id": "tc1"}]}]
        result = inject_noop_tool_if_needed(tools, messages, "github_copilot")
        assert len(result) == 1  # Only original edit tool

    def test_copilot_no_history_no_inject(self):
        messages = [{"role": "user", "content": "hi"}]
        result = inject_noop_tool_if_needed(None, messages, "github_copilot")
        assert result is None

    def test_non_copilot_no_inject(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"id": "tc1"}]},
        ]
        result = inject_noop_tool_if_needed(None, messages, "openai")
        assert result is None

    def test_copilot_empty_tools_with_history(self):
        messages = [{"role": "tool", "content": "result", "tool_call_id": "tc1"}]
        result = inject_noop_tool_if_needed([], messages, "github_copilot")
        assert result is not None
        assert len(result) == 1


class TestHasToolCallsInHistory:
    """_has_tool_calls_in_history() tests."""

    def test_assistant_tool_calls(self):
        assert _has_tool_calls_in_history([
            {"role": "assistant", "tool_calls": [{"id": "tc1"}]},
        ]) is True

    def test_tool_role(self):
        assert _has_tool_calls_in_history([
            {"role": "tool", "content": "result"},
        ]) is True

    def test_anthropic_tool_use(self):
        assert _has_tool_calls_in_history([
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tu1"}]},
        ]) is True

    def test_no_tool_calls(self):
        assert _has_tool_calls_in_history([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]) is False

    def test_empty(self):
        assert _has_tool_calls_in_history([]) is False
