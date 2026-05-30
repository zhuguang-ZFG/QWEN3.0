"""Tests for M5: research orchestration."""

from __future__ import annotations


from research.orchestrator import (
    ResearchQuery,
    ResearchResult,
    _deduplicate,
    _rank,
    _normalize_url,
)
from research.source_adapters import SearchHit


class TestDeduplicate:
    def test_removes_duplicate_urls(self):
        hits = [
            SearchHit(url="https://example.com/a", title="A", snippet="s1"),
            SearchHit(url="https://example.com/a", title="A2", snippet="s2"),
            SearchHit(url="https://example.com/b", title="B", snippet="s3"),
        ]
        result = _deduplicate(hits)
        assert len(result) == 2

    def test_removes_duplicate_titles(self):
        hits = [
            SearchHit(url="https://a.com", title="Same Title", snippet="s1"),
            SearchHit(url="https://b.com", title="Same Title", snippet="s2"),
        ]
        result = _deduplicate(hits)
        assert len(result) == 1

    def test_keeps_unique(self):
        hits = [
            SearchHit(url="https://a.com", title="A", snippet="s1"),
            SearchHit(url="https://b.com", title="B", snippet="s2"),
            SearchHit(url="https://c.com", title="C", snippet="s3"),
        ]
        result = _deduplicate(hits)
        assert len(result) == 3


class TestRank:
    def test_ranks_by_query_term_match(self):
        hits = [
            SearchHit(url="a", title="Python Tutorial", snippet="learn python", score=0.3),
            SearchHit(url="b", title="Java Guide", snippet="learn java", score=0.3),
        ]
        ranked = _rank(hits, "python tutorial")
        assert ranked[0].title == "Python Tutorial"

    def test_ranks_by_score(self):
        hits = [
            SearchHit(url="a", title="Low", snippet="", score=0.2),
            SearchHit(url="b", title="High", snippet="", score=0.9),
        ]
        ranked = _rank(hits, "unrelated query")
        assert ranked[0].title == "High"


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/path/") == "example.com/path"

    def test_lowercases(self):
        assert _normalize_url("https://EXAMPLE.COM/Path") == "example.com/path"


class TestResearchQuery:
    def test_query_dataclass(self):
        q = ResearchQuery(query="FastAPI middleware")
        assert q.query == "FastAPI middleware"
        assert q.max_results_per_source == 5
        assert q.include_code_search is True

    def test_result_dataclass(self):
        r = ResearchResult(query="test", hits=[])
        assert r.query == "test"
        assert r.hits == []
        assert r.duration_ms == 0.0


class TestSynthesizer:
    def test_fallback_synthesis(self):
        from research.synthesizer import _fallback_synthesis
        hits = [
            SearchHit(url="https://a.com", title="Result A", snippet="Content A"),
            SearchHit(url="https://b.com", title="Result B", snippet="Content B"),
        ]
        result = _fallback_synthesis("test query", hits)
        assert "Result A" in result
        assert "Result B" in result
        assert "test query" in result

    def test_empty_hits(self):
        from research.synthesizer import synthesize_results
        result = synthesize_results("query", [])
        assert "No results" in result
