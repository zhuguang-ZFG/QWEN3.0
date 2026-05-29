from context_pipeline.entity_extraction import extract_entities, ExtractedEntities
from context_pipeline.graph_retrieval import (
    CodeGraph,
    RetrievalResult,
    dual_layer_search,
)
from context_pipeline.reranking import rerank_results, format_for_injection


# === Phase 23: Entity Extraction ===

def test_extract_file_paths():
    messages = [{"role": "user", "content": "fix the bug in server.py and routing_engine.py"}]
    entities = extract_entities(messages)
    assert "server.py" in entities.file_paths
    assert "routing_engine.py" in entities.file_paths


def test_extract_functions():
    messages = [{"role": "user", "content": "def route_request is broken, also def classify"}]
    entities = extract_entities(messages)
    assert "route_request" in entities.functions
    assert "classify" in entities.functions


def test_extract_classes():
    messages = [{"role": "user", "content": "class Pipeline has a bug in class RequestContext"}]
    entities = extract_entities(messages)
    assert "Pipeline" in entities.classes
    assert "RequestContext" in entities.classes


def test_extract_errors():
    messages = [{"role": "user", "content": "getting TypeError and ImportError"}]
    entities = extract_entities(messages)
    assert "TypeError" in entities.errors
    assert "ImportError" in entities.errors


def test_extract_technologies():
    messages = [{"role": "user", "content": "using fastapi with asyncio and redis"}]
    entities = extract_entities(messages)
    assert "fastapi" in entities.technologies
    assert "asyncio" in entities.technologies


def test_to_query_terms():
    messages = [{"role": "user", "content": "fix server.py class Pipeline"}]
    entities = extract_entities(messages)
    terms = entities.to_query_terms()
    assert len(terms) > 0


# === Phase 24: Graph-aware Retrieval ===

def test_code_graph_add_and_get():
    graph = CodeGraph()
    graph.add_relation("server.py", "routing_engine.py", "imports")
    graph.add_relation("routing_engine.py", "http_caller.py", "calls")
    related = graph.get_related("server.py", max_depth=2)
    targets = [r.target for r in related]
    assert "routing_engine.py" in targets


def test_dual_layer_search_merges():
    graph = CodeGraph()
    graph.add_relation("server.py", "routing_engine.py", "imports")
    graph.add_relation("server.py", "http_caller.py", "imports")

    vector_results = [
        RetrievalResult(path="routing_engine.py", score=0.9, source="vector"),
        RetrievalResult(path="utils.py", score=0.7, source="vector"),
    ]
    merged = dual_layer_search(["server.py"], vector_results, graph)
    paths = [r.path for r in merged]
    assert "routing_engine.py" in paths
    assert "http_caller.py" in paths


def test_dual_layer_boosts_both_source():
    graph = CodeGraph()
    graph.add_relation("a.py", "b.py", "imports")

    vector_results = [
        RetrievalResult(path="b.py", score=0.8, source="vector"),
    ]
    merged = dual_layer_search(["a.py"], vector_results, graph)
    b_result = next(r for r in merged if r.path == "b.py")
    assert b_result.source == "both"
    assert b_result.score > 0.8


# === Phase 25: Reranking ===

def test_rerank_entity_overlap_boost():
    results = [
        RetrievalResult(path="routing_engine.py", score=0.5, source="vector"),
        RetrievalResult(path="utils.py", score=0.8, source="vector"),
    ]
    reranked = rerank_results(results, query_entities=["routing_engine.py"], top_k=5)
    assert reranked[0].path == "routing_engine.py"


def test_rerank_dual_source_boost():
    results = [
        RetrievalResult(path="a.py", score=0.7, source="vector"),
        RetrievalResult(path="b.py", score=0.6, source="both"),
    ]
    reranked = rerank_results(results, query_entities=[], top_k=5)
    assert reranked[0].path == "b.py"


def test_format_for_injection():
    results = [
        RetrievalResult(path="server.py", score=0.9, source="both", snippet="main app"),
        RetrievalResult(path="utils.py", score=0.5, source="vector"),
    ]
    output = format_for_injection(results)
    assert "[代码上下文]" in output
    assert "server.py" in output
    assert "VG" in output
