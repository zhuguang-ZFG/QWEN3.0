"""Tests for tool_guard — doom loop detection + output truncation."""

import pytest

from tool_guard import DoomLoopGuard, tool_call_identity, truncate_tool_output


class TestDoomLoopGuard:
    def test_no_loop_for_different_tools(self):
        guard = DoomLoopGuard()
        guard.record("read_file", {"path": "a.py"})
        guard.record("write_file", {"path": "b.py"})
        assert not guard.is_doom_loop("read_file", {"path": "a.py"})

    def test_no_loop_for_same_tool_different_args(self):
        guard = DoomLoopGuard()
        guard.record("read_file", {"path": "a.py"})
        guard.record("read_file", {"path": "b.py"})
        guard.record("read_file", {"path": "a.py"})
        assert not guard.is_doom_loop("read_file", {"path": "a.py"})  # not consecutive

    def test_detects_doom_loop_at_threshold(self):
        guard = DoomLoopGuard()
        guard.record("read_file", {"path": "a.py"})
        guard.record("read_file", {"path": "a.py"})
        assert not guard.is_doom_loop("read_file", {"path": "a.py"})  # 2, not yet
        guard.record("read_file", {"path": "a.py"})
        assert guard.is_doom_loop("read_file", {"path": "a.py"})  # 3, triggered

    def test_inject_correction_returns_message(self):
        guard = DoomLoopGuard()
        msg = guard.inject_correction()
        assert "stuck in a loop" in msg

    def test_normalize_args_equivalent(self):
        guard = DoomLoopGuard()
        guard.record("tool", {"b": 2, "a": 1})
        guard.record("tool", {"a": 1, "b": 2})  # different order, same content
        guard.record("tool", {"b": 2, "a": 1})  # 3rd call
        assert guard.is_doom_loop("tool", {"a": 1, "b": 2})


class TestTruncateToolOutput:
    def test_short_output_not_truncated(self):
        output = "hello world"
        result, meta = truncate_tool_output(output, max_chars=100)
        assert result == output
        assert meta["truncated"] is False

    def test_long_output_truncated(self):
        output = "x" * 20_000
        result, meta = truncate_tool_output(output, max_chars=100)
        assert len(result) < len(output)
        assert meta["truncated"] is True
        assert "truncated" in result.lower()
        assert meta["original_sha256"]

    def test_exact_boundary_not_truncated(self):
        output = "x" * 100
        result, meta = truncate_tool_output(output, max_chars=100)
        assert meta["truncated"] is False

    def test_sha256_deterministic(self):
        result1, meta1 = truncate_tool_output("A" * 20_000, max_chars=100)
        result2, meta2 = truncate_tool_output("A" * 20_000, max_chars=100)
        assert meta1["original_sha256"] == meta2["original_sha256"]


class TestToolCallIdentity:
    def test_same_args_same_hash(self):
        h1 = tool_call_identity("read", {"path": "a.py"})
        h2 = tool_call_identity("read", {"path": "a.py"})
        assert h1 == h2

    def test_different_tools_different_hash(self):
        h1 = tool_call_identity("read", {"path": "a.py"})
        h2 = tool_call_identity("write", {"path": "a.py"})
        assert h1 != h2

    def test_normalizes_arg_order(self):
        h1 = tool_call_identity("tool", {"b": 2, "a": 1})
        h2 = tool_call_identity("tool", {"a": 1, "b": 2})
        assert h1 == h2
