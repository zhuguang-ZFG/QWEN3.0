"""Tests for routing_engine coding context injection.

code_orchestrator_context retired; coding context now flows through
routing_engine.route() → lima_context.build_context_digest().
"""

from __future__ import annotations


def test_lima_context_returns_empty_for_chat():
    """Non-coding queries should not get context injection."""
    from lima_context import build_context_digest

    result = build_context_digest(
        "hello",
        [{"role": "user", "content": "hello"}],
    )
    assert result == ""


def test_lima_context_extracts_file_path():
    """Coding queries with file paths should get context."""
    from lima_context import build_context_digest

    result = build_context_digest(
        "Fix server.py",
        [{"role": "user", "content": "Fix D:\\project\\server.py\nTypeError: bad"}],
        ide_source="Claude Code",
    )
    assert "server.py" in result
