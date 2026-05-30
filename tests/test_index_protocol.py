"""Tests for context_pipeline.index_protocol in-memory fixtures."""
from context_pipeline.index_protocol import (
    IndexEntry,
    InMemoryVectorIndex,
    VectorIndex,
)


def test_in_memory_vector_index_returns_fixture_matches():
    fixture = {
        "routing": [IndexEntry(path="routing_engine.py", content="...", symbols=["route", "classify"])],
        "health": [
            IndexEntry(path="health_tracker.py", content="...", symbols=["record_success"]),
            IndexEntry(path="health_tracker.py", content="...", symbols=["compute_score"]),
        ],
    }
    idx = InMemoryVectorIndex(fixture)
    results = idx.search("routing query about routes", limit=2)
    assert len(results) == 1
    assert results[0].path == "routing_engine.py"


def test_in_memory_vector_index_falls_back_to_all_entries():
    idx = InMemoryVectorIndex()
    idx.add(IndexEntry(path="server.py"))
    idx.add(IndexEntry(path="router_v3.py"))
    assert idx.entry_count == 2
    results = idx.search("no fixture match", limit=5)
    assert len(results) == 2


def test_in_memory_vector_index_no_fixture():
    idx = InMemoryVectorIndex()
    assert idx.entry_count == 0
    assert idx.search("anything") == []


def test_vector_index_protocol_is_abc():
    msg = ""
    try:
        class BadIndex(VectorIndex):
            pass
        BadIndex()
    except TypeError:
        msg = "abc"
    assert msg == "abc"
