"""Tests for context_pipeline/code_context_injection.py (P2-7)."""

from __future__ import annotations

from pathlib import Path

import pytest

import context_pipeline.code_context_injection as cci


class TestExtractFileMentions:
    def test_extracts_python_file_paths(self):
        file_patterns, identifiers = cci.extract_file_mentions("see server.py and app.js")
        assert "server.py" in file_patterns
        assert "app.js" in file_patterns

    def test_extracts_class_and_function_like_identifiers(self):
        _, identifiers = cci.extract_file_mentions("Use RouterConfig and handle_error")
        assert "RouterConfig" in identifiers
        assert "handle_error" in identifiers

    def test_includes_recent_messages(self):
        messages = [
            {"role": "user", "content": "check models.py"},
            {"role": "assistant", "content": "ok"},
        ]
        file_patterns, _ = cci.extract_file_mentions("fix bug", messages)
        assert "models.py" in file_patterns

    def test_caps_identifiers(self):
        _, identifiers = cci.extract_file_mentions("a b c d e f g h i j k l m n o p")
        assert len(identifiers) <= 10


class TestScanAndBuildContext:
    @pytest.fixture
    def project_tmp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cci, "_PROJECT_ROOT", str(tmp_path))
        return tmp_path

    def test_returns_empty_when_no_context(self, project_tmp, monkeypatch):
        monkeypatch.setattr(cci, "_resolve_file", lambda _fname: None)
        monkeypatch.setattr(cci, "_scan_single_file", lambda _p: "")
        monkeypatch.setattr(
            cci,
            "_phase_semantic_retrieval",
            lambda _q, _m, parts, total, scanned, _maxc: (parts, total, scanned),
        )
        monkeypatch.setattr(cci, "_find_identifier_files", lambda _i: [])
        assert cci.scan_and_build_context("hello") == ""

    def test_includes_direct_file_mentions(self, project_tmp, monkeypatch):
        server = project_tmp / "server.py"
        server.write_text("x = 1")

        def _fake_scan(path: Path) -> str:
            return f"## {path.name}"

        monkeypatch.setattr(cci, "_scan_single_file", _fake_scan)
        monkeypatch.setattr(
            cci,
            "_phase_semantic_retrieval",
            lambda _q, _m, parts, total, scanned, _maxc: (parts, total, scanned),
        )
        monkeypatch.setattr(cci, "_find_identifier_files", lambda _i: [])

        result = cci.scan_and_build_context("check server.py")
        assert "server.py" in result
        assert "## server.py" in result

    def test_includes_semantic_retrieval(self, project_tmp, monkeypatch):
        server = project_tmp / "server.py"
        server.write_text("x = 1")

        def _fake_semantic(_q, _m, parts, total, scanned, _maxc):
            parts.append("[semantic] helper")
            return parts, total + 20, scanned

        monkeypatch.setattr(cci, "_scan_single_file", lambda _p: "")
        monkeypatch.setattr(cci, "_phase_semantic_retrieval", _fake_semantic)
        monkeypatch.setattr(cci, "_find_identifier_files", lambda _i: [])

        result = cci.scan_and_build_context("check server.py")
        assert "[semantic] helper" in result

    def test_includes_identifier_search_results(self, project_tmp, monkeypatch):
        utils = project_tmp / "utils.py"
        utils.write_text("def helper(): pass")

        def _fake_find(identifier: str) -> list[Path]:
            return [utils] if identifier == "helper" else []

        def _fake_scan(path: Path) -> str:
            return f"## {path.name}"

        monkeypatch.setattr(cci, "_scan_single_file", _fake_scan)
        monkeypatch.setattr(
            cci,
            "_phase_semantic_retrieval",
            lambda _q, _m, parts, total, scanned, _maxc: (parts, total, scanned),
        )
        monkeypatch.setattr(cci, "_find_identifier_files", _fake_find)

        result = cci.scan_and_build_context("how does helper work")
        assert "utils.py" in result

    def test_respects_max_chars(self, project_tmp, monkeypatch):
        server = project_tmp / "server.py"
        server.write_text("x = 1")

        def _fake_scan(_p: Path) -> str:
            return "a" * 500

        monkeypatch.setattr(cci, "_scan_single_file", _fake_scan)
        monkeypatch.setattr(
            cci,
            "_phase_semantic_retrieval",
            lambda _q, _m, parts, total, scanned, _maxc: (parts, total, scanned),
        )
        monkeypatch.setattr(cci, "_find_identifier_files", lambda _i: [])

        result = cci.scan_and_build_context("check server.py", max_chars=100)
        # Header alone is <100 chars, so direct mention should be excluded by budget.
        assert result == ""
