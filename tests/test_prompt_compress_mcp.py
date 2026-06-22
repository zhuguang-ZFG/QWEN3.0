"""Tests for prompt_compress MCP helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_COMPRESS_PATH = Path(__file__).resolve().parents[1] / "lima_mcp_stdio" / "prompt_compress_mcp.py"
_spec = importlib.util.spec_from_file_location("prompt_compress_mcp", _COMPRESS_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_compress_text_skips_short_input():
    text = "hello"
    assert _mod.compress_text(text) == text


def test_should_compress_threshold():
    short_ok, short_tokens = _mod._should_compress("x" * 50, min_chars=200)
    long_ok, long_tokens = _mod._should_compress("x" * 800, min_chars=200)
    assert short_ok is False
    assert long_ok is True
    assert long_tokens > short_tokens
