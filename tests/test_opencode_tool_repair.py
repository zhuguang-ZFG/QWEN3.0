"""Tests for opencode_tool_repair.py — tool name auto-repair + invalid routing."""

import json
import pytest
from opencode_tool_repair import (
    repair_tool_name,
    build_invalid_tool_result,
    build_invalid_tool_input_json,
    get_invalid_tool_definition,
    repair_tool_calls_in_body,
    should_inject_invalid_tool,
    INVALID_TOOL_NAME,
)


# ── repair_tool_name ─────────────────────────────────────────────────────────


class TestRepairToolName:
    def test_exact_match(self):
        assert repair_tool_name("read_file", ["read_file", "write_file"]) == "read_file"

    def test_case_insensitive_match(self):
        assert repair_tool_name("Read_File", ["read_file", "write_file"]) == "read_file"

    def test_uppercase_match(self):
        assert repair_tool_name("READ_FILE", ["read_file"]) == "read_file"

    def test_mixed_case_match(self):
        assert repair_tool_name("ReadFile", ["readfile", "writefile"]) == "readfile"

    def test_no_match(self):
        assert repair_tool_name("delete_file", ["read_file", "write_file"]) is None

    def test_empty_name(self):
        assert repair_tool_name("", ["read_file"]) is None

    def test_dict_available_tools(self):
        tools = {"read_file": {"type": "function"}, "write_file": {"type": "function"}}
        assert repair_tool_name("READ_FILE", tools) == "read_file"

    def test_empty_tools(self):
        assert repair_tool_name("read_file", []) is None


# ── build_invalid_tool_result ────────────────────────────────────────────────


class TestBuildInvalidToolResult:
    def test_basic(self):
        result = build_invalid_tool_result("bad_tool", "not found")
        assert result == {"tool": "bad_tool", "error": "not found"}

    def test_default_error(self):
        result = build_invalid_tool_result("x")
        assert result["error"] == "Tool not found"

    def test_json_serializable(self):
        result = build_invalid_tool_input_json("bad", "err")
        parsed = json.loads(result)
        assert parsed["tool"] == "bad"
        assert parsed["error"] == "err"


# ── get_invalid_tool_definition ──────────────────────────────────────────────


class TestGetInvalidToolDefinition:
    def test_structure(self):
        tool = get_invalid_tool_definition()
        assert tool["type"] == "function"
        assert tool["function"]["name"] == INVALID_TOOL_NAME
        assert "parameters" in tool["function"]

    def test_name_is_invalid(self):
        tool = get_invalid_tool_definition()
        assert tool["function"]["name"] == "invalid"

    def test_has_required_fields(self):
        tool = get_invalid_tool_definition()
        params = tool["function"]["parameters"]
        assert "tool" in params["properties"]
        assert "error" in params["properties"]
        assert "tool" in params["required"]


# ── repair_tool_calls_in_body ───────────────────────────────────────────────


class TestRepairToolCallsInBody:
    def _make_body(self, messages, tools=None):
        body = {"messages": messages}
        if tools is not None:
            body["tools"] = tools
        return body

    def _make_tool(self, name):
        return {
            "type": "function",
            "function": {"name": name, "parameters": {"type": "object"}},
        }

    def test_no_repair_needed(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "read_file", "arguments": "{}"}}
            ]}],
            [self._make_tool("read_file")],
        )
        result = repair_tool_calls_in_body(body)
        assert result["messages"][0]["tool_calls"][0]["function"]["name"] == "read_file"

    def test_case_repair(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "READ_FILE", "arguments": "{}"}}
            ]}],
            [self._make_tool("read_file")],
        )
        result = repair_tool_calls_in_body(body)
        assert result["messages"][0]["tool_calls"][0]["function"]["name"] == "read_file"

    def test_unknown_routed_to_invalid(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "delete_all", "arguments": "{}"}}
            ]}],
            [self._make_tool("read_file")],
        )
        result = repair_tool_calls_in_body(body)
        tc = result["messages"][0]["tool_calls"][0]
        assert tc["function"]["name"] == INVALID_TOOL_NAME
        args = json.loads(tc["function"]["arguments"])
        assert args["tool"] == "delete_all"

    def test_invalid_tool_added_to_tools(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "unknown", "arguments": "{}"}}
            ]}],
            [self._make_tool("read_file")],
        )
        result = repair_tool_calls_in_body(body)
        tool_names = [t["function"]["name"] for t in result["tools"]]
        assert INVALID_TOOL_NAME in tool_names

    def test_no_messages(self):
        body = {"model": "test"}
        result = repair_tool_calls_in_body(body)
        assert result == body

    def test_no_tool_calls(self):
        body = self._make_body([{"role": "user", "content": "hello"}])
        result = repair_tool_calls_in_body(body)
        assert result == body

    def test_explicit_tool_names(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "WRITE", "arguments": "{}"}}
            ]}],
        )
        result = repair_tool_calls_in_body(body, available_tool_names=["write", "read"])
        assert result["messages"][0]["tool_calls"][0]["function"]["name"] == "write"

    def test_multiple_tool_calls_mixed(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "read_file", "arguments": "{}"}},
                {"id": "c2", "function": {"name": "UNKNOWN", "arguments": "{}"}},
            ]}],
            [self._make_tool("read_file")],
        )
        result = repair_tool_calls_in_body(body)
        calls = result["messages"][0]["tool_calls"]
        assert calls[0]["function"]["name"] == "read_file"
        assert calls[1]["function"]["name"] == INVALID_TOOL_NAME

    def test_does_not_mutate_original(self):
        body = self._make_body(
            [{"role": "assistant", "tool_calls": [
                {"id": "c1", "function": {"name": "BAD", "arguments": "{}"}}
            ]}],
            [self._make_tool("bad")],
        )
        original_name = body["messages"][0]["tool_calls"][0]["function"]["name"]
        repair_tool_calls_in_body(body)
        assert body["messages"][0]["tool_calls"][0]["function"]["name"] == original_name


# ── should_inject_invalid_tool ───────────────────────────────────────────────


class TestShouldInjectInvalidTool:
    def test_empty_tools(self):
        assert should_inject_invalid_tool([]) is False

    def test_tools_without_invalid(self):
        tools = [{"type": "function", "function": {"name": "read_file"}}]
        assert should_inject_invalid_tool(tools) is True

    def test_tools_with_invalid(self):
        tools = [
            {"type": "function", "function": {"name": "read_file"}},
            {"type": "function", "function": {"name": INVALID_TOOL_NAME}},
        ]
        assert should_inject_invalid_tool(tools) is False

    def test_none_tools(self):
        assert should_inject_invalid_tool(None) is False
