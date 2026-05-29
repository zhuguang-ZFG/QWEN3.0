"""Tests for context_pipeline.reranker_protocol."""
from context_pipeline.reranker_protocol import (
    FixtureReranker,
    LocalReranker,
    Reranker,
    ScoredCandidate,
)


def _mk(path: str, score: float, source: str = "vector") -> ScoredCandidate:
    return ScoredCandidate(path=path, score=score, source=source)


def test_local_reranker_ranks_by_entity_overlap():
    reranker = LocalReranker()
    candidates = [
        _mk("routing_engine.py", 0.7, "vector"),
        _mk("server.py", 0.5, "vector"),
        _mk("health_tracker.py", 0.5, "graph"),
    ]
    ranked = reranker.rerank(candidates, ["routing_engine"], top_k=2)
    assert ranked[0].path == "routing_engine.py"


def test_local_reranker_bonus_for_dual_source():
    reranker = LocalReranker()
    candidates = [
        _mk("a.py", 1.0, "vector"),
        _mk("b.py", 0.6, "both"),
    ]
    ranked = reranker.rerank(candidates, ["b"], top_k=2)
    assert ranked[0].path == "b.py"


def test_local_reranker_does_not_mutate_input_scores():
    reranker = LocalReranker()
    candidates = [
        _mk("routing_engine.py", 0.7, "both"),
        _mk("server.py", 0.5, "vector"),
    ]

    first = reranker.rerank(candidates, ["routing_engine"], top_k=2)
    second = reranker.rerank(candidates, ["routing_engine"], top_k=2)

    assert [candidate.score for candidate in candidates] == [0.7, 0.5]
    assert [candidate.score for candidate in first] == [candidate.score for candidate in second]


def test_local_reranker_format_context():
    reranker = LocalReranker()
    results = [
        ScoredCandidate(path="routing_engine.py", score=0.85, source="both", snippet="def route("),
        ScoredCandidate(path="server.py", score=0.72, source="vector", snippet="app = FastAPI()"),
    ]
    ctx = reranker.format_context(results)
    assert "[VG]" in ctx
    assert "routing_engine.py" in ctx
    assert "server.py" in ctx
    assert "score:0.85" in ctx


def test_fixture_reranker_returns_fixed_results():
    fixture = {
        "routing": [_mk("routing_engine.py", 0.99, "both")],
        "health": [_mk("health_tracker.py", 0.85, "vector")],
    }
    reranker = FixtureReranker(fixture)
    ranked = reranker.rerank(
        [_mk("unused.py", 0.1)],
        ["routing", "health"],
    )
    assert len(ranked) == 2
    assert ranked[0].path == "routing_engine.py"
    assert ranked[1].path == "health_tracker.py"


def test_fixture_reranker_falls_back_to_input_when_no_fixture_match():
    reranker = FixtureReranker()
    candidates = [_mk("server.py", 0.5)]
    ranked = reranker.rerank(candidates, ["unknown"], top_k=3)
    assert ranked == candidates


def test_reranker_is_abstract():
    msg = ""
    try:
        class BadReranker(Reranker):
            pass
        BadReranker()
    except TypeError:
        msg = "abc"
    assert msg == "abc"
