"""Tests for context_pipeline/reranking.py — retrieval result reranking."""

from context_pipeline.reranking import rerank_results, format_for_injection
from context_pipeline.graph_retrieval import RetrievalResult


def _make_result(path: str, source: str = "vector", score: float = 1.0, relations=None):
    return RetrievalResult(path=path, source=source, score=score, relations=relations or [])


class TestRerankResults:
    def test_empty_results(self):
        assert rerank_results([], []) == []

    def test_single_result(self):
        results = [_make_result("src/main.py")]
        ranked = rerank_results(results, [], top_k=5)
        assert len(ranked) == 1

    def test_entity_overlap_bonus(self):
        results = [
            _make_result("src/main.py"),
            _make_result("src/utils.py"),
        ]
        ranked = rerank_results(results, ["main"], top_k=5)
        assert ranked[0].path == "src/main.py"

    def test_dual_source_bonus(self):
        results = [
            _make_result("a.py", source="vector", score=1.0),
            _make_result("a.py", source="both", score=1.0),
        ]
        ranked = rerank_results(results, [], top_k=5)
        assert ranked[0].source == "both"

    def test_top_k_limit(self):
        results = [_make_result(f"f{i}.py") for i in range(10)]
        ranked = rerank_results(results, [], top_k=3)
        assert len(ranked) == 3


class TestFormatForInjection:
    def test_empty_results(self):
        assert format_for_injection([]) == ""

    def test_contains_code_context_header(self):
        result = format_for_injection([_make_result("test.py", source="vector")])
        assert "[代码上下文]" in result

    def test_contains_file_path(self):
        result = format_for_injection([_make_result("src/app.py", source="graph")])
        assert "src/app.py" in result
