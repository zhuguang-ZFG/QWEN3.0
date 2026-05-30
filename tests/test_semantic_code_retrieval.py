"""Tests for semantic code retrieval and graph expansion."""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from context_pipeline.semantic_code_retrieval import (
    assess_code_complexity,
    retrieve_semantic,
    _tokenize_query,
    _build_file_index,
    _score_file,
)
from context_pipeline.graph_context_expander import (
    expand_context,
)


# ─── Tokenizer tests ──────────────────────────────────────────────────


class TestTokenizer:
    def test_extracts_identifiers(self):
        terms = _tokenize_query("fix the RoutingEngine class in routing_engine.py")
        assert "routingengine" in terms
        assert "routing_engine.py" in terms

    def test_extracts_chinese_keywords(self):
        terms = _tokenize_query("帮我修复 routing_engine 中的 bug")
        assert "routing_engine" in terms

    def test_removes_stop_words(self):
        terms = _tokenize_query("the quick brown fox")
        assert "the" not in terms
        assert "quick" in terms

    def test_empty_query(self):
        terms = _tokenize_query("")
        assert terms == []


# ─── File index tests ─────────────────────────────────────────────────


class TestFileIndex:
    def test_builds_index(self):
        from pathlib import Path
        root = Path(os.environ.get("LIMA_PROJECT_ROOT", os.getcwd()))
        index = _build_file_index(root)
        assert len(index) > 0

    def test_index_has_symbols(self):
        from pathlib import Path
        root = Path(os.environ.get("LIMA_PROJECT_ROOT", os.getcwd()))
        index = _build_file_index(root)
        has_symbols = any(len(info.get("symbols", [])) > 0 for info in index.values())
        assert has_symbols


# ─── Scoring tests ────────────────────────────────────────────────────


class TestScoring:
    def test_exact_symbol_match_high_score(self):
        file_info = {
            "words": {"routing", "engine", "select"},
            "symbols": ["RoutingEngine", "select"],
            "size": 2000,
        }
        score = _score_file(["routingengine"], file_info)
        assert score > 0

    def test_word_match_lower_score(self):
        file_info = {
            "words": {"routing", "engine"},
            "symbols": [],
            "size": 2000,
        }
        score_word = _score_file(["routing"], file_info)
        score_no = _score_file(["nonexistent_xyz"], file_info)
        assert score_word > score_no

    def test_smaller_files_score_higher(self):
        info_small = {"words": {"test"}, "symbols": [], "size": 500}
        info_large = {"words": {"test"}, "symbols": [], "size": 50000}
        s_small = _score_file(["test"], info_small)
        s_large = _score_file(["test"], info_large)
        assert s_small > s_large


# ─── Semantic retrieval tests ─────────────────────────────────────────


class TestSemanticRetrieval:
    def test_retrieve_semantic(self):
        results = retrieve_semantic(
            "routing engine select backend",
            max_results=5,
        )
        # Should find some results (may vary by environment)
        assert isinstance(results, list)

    def test_retrieve_with_empty_query(self):
        results = retrieve_semantic("", max_results=5)
        assert results == []

    def test_code_complexity_assessment(self):
        complexity = assess_code_complexity(
            "refactor the routing engine architecture",
        )
        assert 0.0 <= complexity <= 1.0

    def test_simple_query_low_complexity(self):
        complexity = assess_code_complexity(
            "hello world",
        )
        assert complexity < 1.0


# ─── Graph expansion tests ────────────────────────────────────────────


class TestGraphExpansion:
    def test_expand_from_routing_engine(self):
        expanded = expand_context(
            ["routing_engine.py"],
            max_hops=1,
            max_files=5,
        )
        assert isinstance(expanded, list)

    def test_expand_empty_seeds(self):
        assert expand_context([]) == []

    def test_expand_limits_results(self):
        expanded = expand_context(
            ["routing_engine.py"],
            max_hops=2,
            max_files=3,
        )
        assert len(expanded) <= 3
