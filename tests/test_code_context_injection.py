"""Tests for context_pipeline/code_context_injection.py (v3.0 deprecated)."""

from __future__ import annotations

import context_pipeline.code_context_injection as cci


def test_extract_file_mentions_returns_empty():
    assert cci.extract_file_mentions("see server.py and app.js") == ([], [])


def test_scan_and_build_context_returns_empty():
    assert cci.scan_and_build_context("check server.py") == ""
