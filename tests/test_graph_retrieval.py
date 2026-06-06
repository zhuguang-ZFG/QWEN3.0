"""Tests for context_pipeline: graph_retrieval, reranking, entity_extraction, retrieval_eval."""
from context_pipeline.graph_retrieval import (
    CodeGraph,
    RetrievalResult,
    dual_layer_search,
)
from context_pipeline.reranking import format_for_injection, rerank_results
from context_pipeline.retrieval_eval import (
    RetrievalQuery,
    compute_precision_at_k,
    compute_recall,
    compute_reciprocal_rank,
    evaluate_queries,
    evaluate_single,
    format_summary,
)

# -- CodeGraph ------------------------------------------------------------------

def test_code_graph_add_and_get_related():
    g = CodeGraph()
    g.add_relation("a.py", "b.py", "imports")
    g.add_relation("a.py", "X", "defines_class")

    related = g.get_related("a.py", max_depth=1)
    assert len(related) >= 2


def test_code_graph_bfs_depth():
    g = CodeGraph()
    g.add_relation("a", "b", "imports")
    g.add_relation("b", "c", "imports")
    g.add_relation("c", "d", "imports")

    # depth=0: process only start node, get its outgoing edges
    d0 = {r.target for r in g.get_related("a", max_depth=0)}
    assert "b" in d0
    assert "c" not in d0

    # depth=2: process a, b, c - get edges from all three
    d2 = {r.target for r in g.get_related("a", max_depth=2)}
    assert "c" in d2


def test_code_graph_edge_count():
    g = CodeGraph()
    assert g.edge_count == 0
    g.add_relation("a", "b", "imports")
    assert g.edge_count == 1


# -- dual_layer_search ----------------------------------------------------------

def test_dual_layer_search_merges_sources():
    g = CodeGraph()
    g.add_relation("mod_a.py", "mod_b.py", "imports")

    vector_results = [
        RetrievalResult(path="mod_b.py", score=0.8, source="vector"),
        RetrievalResult(path="utils.py", score=0.6, source="vector"),
    ]

    merged = dual_layer_search(["mod_a.py"], vector_results, g, max_results=10)
    assert len(merged) >= 2

    mod_b = next(r for r in merged if r.path == "mod_b.py")
    assert mod_b.source == "both"
    assert mod_b.score >= 0.8


def test_dual_layer_search_discovers_graph_only_results():
    g = CodeGraph()
    g.add_relation("mod_a.py", "unknown_utils.py", "imports")

    merged = dual_layer_search(["mod_a.py"], [], g, max_results=10)
    assert len(merged) >= 1
    assert merged[0].source == "graph"


def test_dual_layer_search_respects_max_results():
    g = CodeGraph()
    for i in range(20):
        g.add_relation("hub.py", f"leaf_{i}.py", "imports")

    merged = dual_layer_search(["hub"], [], g, max_results=5)
    assert len(merged) <= 5


# -- reranking ------------------------------------------------------------------

def test_rerank_results_promotes_entity_overlap():
    results = [
        RetrievalResult(path="routing_engine.py", score=0.7, source="vector"),
        RetrievalResult(path="http_caller.py", score=0.7, source="vector"),
    ]
    # Entity overlap uses exact path-component match
    reranked = rerank_results(results, ["routing_engine.py"], top_k=5)

    assert reranked[0].path == "routing_engine.py"
    assert reranked[0].score > 0.7


def test_rerank_results_promotes_dual_source():
    results = [
        RetrievalResult(path="dual_hit.py", score=0.7, source="both"),
        RetrievalResult(path="single_hit.py", score=0.9, source="vector"),
    ]
    reranked = rerank_results(results, [], top_k=5)

    # dual_hit gets +0.3 bonus, giving 1.0 vs single_hit's 0.9
    assert reranked[0].path == "dual_hit.py"


def test_rerank_results_respects_top_k():
    results = [
        RetrievalResult(path=f"file_{i}.py", score=0.5, source="vector")
        for i in range(10)
    ]
    reranked = rerank_results(results, [], top_k=3)
    assert len(reranked) == 3


def test_format_for_injection_produces_compact_output():
    results = [
        RetrievalResult(path="routing_engine.py", score=0.92, source="vector"),
        RetrievalResult(path="http_caller.py", score=0.85, source="both",
                        relations=["imports:server"]),
    ]
    output = format_for_injection(results, max_chars=800)
    assert "routing_engine.py" in output
    assert "http_caller.py" in output
    assert "[VG]" in output or "VG" in output


def test_format_for_injection_respects_max_chars():
    results = [
        RetrievalResult(path=f"very_long_path_name_file_{i}.py", score=0.9, source="vector")
        for i in range(20)
    ]
    output = format_for_injection(results, max_chars=200)
    assert len(output) <= 210  # small tolerance


def test_format_for_injection_empty():
    assert format_for_injection([]) == ""


# -- retrieval_eval -------------------------------------------------------------

def test_compute_recall_full():
    assert compute_recall(["a.py", "b.py"], ["a.py", "b.py", "c.py"]) == 1.0


def test_compute_recall_partial():
    assert compute_recall(["a.py", "b.py", "c.py"], ["a.py"]) == 1.0 / 3.0


def test_compute_recall_empty_expected():
    assert compute_recall([], ["a.py"]) == 1.0


def test_compute_precision_at_k():
    expected = ["a.py", "b.py"]
    retrieved = ["a.py", "c.py", "d.py"]
    assert compute_precision_at_k(expected, retrieved, k=2) == 0.5
    assert compute_precision_at_k(expected, retrieved, k=1) == 1.0


def test_compute_reciprocal_rank_first():
    assert compute_reciprocal_rank(["target"], ["target", "a", "b"]) == 1.0


def test_compute_reciprocal_rank_third():
    assert compute_reciprocal_rank(["target"], ["a", "b", "target"]) == 1.0 / 3.0


def test_compute_reciprocal_rank_miss():
    assert compute_reciprocal_rank(["target"], ["a", "b", "c"]) == 0.0


def test_evaluate_single():
    q = RetrievalQuery(query="find routing", expected_paths=["routing_engine.py"])
    result = evaluate_single(q, ["routing_engine.py", "http_caller.py"])
    assert result.hit is True
    assert result.recall == 1.0
    assert result.reciprocal_rank == 1.0


def test_evaluate_single_miss():
    q = RetrievalQuery(query="find routing", expected_paths=["routing_engine.py"])
    result = evaluate_single(q, ["other.py"])
    assert result.hit is False
    assert result.recall == 0.0


def test_evaluate_queries_summary():
    queries = [
        RetrievalQuery("q1", ["a.py"]),
        RetrievalQuery("q2", ["b.py"]),
    ]
    retrieved = [["a.py", "c.py"], ["x.py"]]
    summary = evaluate_queries(queries, retrieved, k=5)
    assert summary.queries == 2
    assert summary.hit_rate == 0.5
    assert summary.mean_recall == 0.5


def test_evaluate_queries_counts_missing_retrieval_as_miss():
    queries = [
        RetrievalQuery("q1", ["a.py"]),
        RetrievalQuery("q2", ["b.py"]),
    ]
    summary = evaluate_queries(queries, [["a.py"]], k=5)

    assert summary.queries == 2
    assert summary.results[1].retrieved_paths == []
    assert summary.hit_rate == 0.5


def test_format_summary():
    q = RetrievalQuery("test", ["a.py"])
    result = evaluate_single(q, ["a.py"])
    from context_pipeline.retrieval_eval import EvalSummary
    summary = EvalSummary(
        queries=1, mean_recall=1.0, mean_precision_at_k=1.0,
        hit_rate=1.0, mean_mrr=1.0, results=[result],
    )
    text = format_summary(summary)
    assert "Queries: 1" in text
    assert "Recall" in text and "1.000" in text
    assert "Hit Rate" in text
