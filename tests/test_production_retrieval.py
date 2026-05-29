"""Production retrieval wiring tests."""

from context_pipeline.code_scanner import refresh_graph, reset_code_graph
from context_pipeline.production_index import (
    reset_production_index,
    search_production_corpus,
)
from context_pipeline.retrieval_corpus import resolve_production_corpus_paths
from context_pipeline.retrieval_injection import run_retrieval


def setup_function():
    reset_production_index()
    reset_code_graph()


def test_resolve_production_corpus_paths_includes_routing_modules():
    paths = resolve_production_corpus_paths()
    basenames = {path.split("\\")[-1].split("/")[-1] for path in paths}

    assert "routing_engine.py" in basenames
    assert "http_caller.py" in basenames
    assert "retrieval_injection.py" in basenames


def test_production_index_searches_routing_engine():
    hits = search_production_corpus(
        "classify ide chat vision request type routing engine",
        top_k=5,
    )

    assert hits
    assert any(
        "routing_engine.py" in hit.path or "routing_classifier.py" in hit.path
        for hit in hits
    )


def test_run_retrieval_uses_production_index_for_file_entities():
    payload = run_retrieval([
        {"role": "user", "content": "fix routing_engine.py select backend health"},
    ])

    assert payload is not None
    assert payload.text
    assert "routing_engine.py" in payload.text or "routing_selector.py" in payload.text


def test_code_graph_scans_production_corpus():
    graph = refresh_graph()
    assert graph.edge_count >= 3
