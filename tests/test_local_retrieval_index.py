"""In-memory token index and FTS5 index tests for the local retrieval lab."""

from local_retrieval.fts_index import FtsIndex
from local_retrieval.index import InMemoryTokenIndex, RetrievalHit


def test_in_memory_token_index_add_and_search_returns_path_and_own_snippet(tmp_path):
    index = InMemoryTokenIndex(index_id="test-idx", max_chars=120)
    first = tmp_path / "doc_a.txt"
    second = tmp_path / "doc_b.txt"
    first.write_text("alpha routing engine health\n" * 10, encoding="utf-8")
    second.write_text("beta gradient descent optimizer\n" * 10, encoding="utf-8")
    index.add_documents([str(first), str(second)])

    hits = index.search("gradient descent", top_k=3)

    assert len(hits) >= 1
    assert hits[0].score > 0
    assert hits[0].document_path == str(second)
    assert "gradient" in hits[0].reason
    assert "gradient" in hits[0].snippet


def test_in_memory_token_index_empty_and_zero_top_k_search():
    index = InMemoryTokenIndex()

    assert index.search("nothing") == []
    assert index.search("", top_k=5) == []
    assert index.search("nothing", top_k=0) == []


def test_in_memory_token_index_stats():
    index = InMemoryTokenIndex(index_id="stats-test")

    assert index.stats()["index_id"] == "stats-test"
    assert index.stats()["chunk_count"] == 0


def test_in_memory_token_index_build_manifest_contains_chunk_records(tmp_path):
    index = InMemoryTokenIndex(index_id="manifest-test")
    file_path = tmp_path / "code.py"
    file_path.write_text("def hello():\n    return 'world'\n" * 10, encoding="utf-8")
    index.add_documents([str(file_path)])

    manifest = index.build_manifest()

    assert manifest.index_id == "manifest-test"
    assert manifest.document_count == 1
    assert manifest.chunk_count >= 1
    assert manifest.documents[0].chunks[0].document_path == str(file_path)
    assert manifest.to_dict()["documents"][0]["path"] == "code.py"


def test_in_memory_token_index_search_reason_and_hit_to_dict_redact(tmp_path):
    index = InMemoryTokenIndex()
    file_path = tmp_path / "doc.txt"
    file_path.write_text(
        "machine learning models use gradient descent for optimization\n" * 10,
        encoding="utf-8",
    )
    index.add_documents([str(file_path)])

    hits = index.search("gradient descent", top_k=3)
    redacted = RetrievalHit(
        chunk_id="sk-secret",
        document_path="/tmp/sk-secret.py",
        score=1.0,
        reason="Bearer token",
        snippet="api_key=secret",
    ).to_dict()

    assert len(hits) >= 1
    assert "gradient" in hits[0].reason.lower()
    assert redacted["chunk_id"] == "[REDACTED]"
    assert redacted["document_path"] == "[REDACTED]"
    assert redacted["reason"] == "[REDACTED]"
    assert redacted["snippet"] == "[REDACTED]"


def test_in_memory_token_index_add_nonexistent_file():
    index = InMemoryTokenIndex()

    count = index.add_documents(["/nonexistent/path.txt"])

    assert count == 0


def test_in_memory_token_index_search_order_is_deterministic(tmp_path):
    index = InMemoryTokenIndex(index_id="order-test", max_chars=80)
    file_path = tmp_path / "doc.txt"
    file_path.write_text("alpha beta\n" * 20, encoding="utf-8")
    index.add_documents([str(file_path)])

    first = [hit.chunk_id for hit in index.search("alpha", top_k=5)]
    second = [hit.chunk_id for hit in index.search("alpha", top_k=5)]

    assert first == second


# FTS5 Index tests


def test_fts_index_add_and_search_returns_results(tmp_path):
    index = FtsIndex(index_id="fts-test", max_chars=120)
    first = tmp_path / "doc_a.txt"
    second = tmp_path / "doc_b.txt"
    first.write_text("alpha routing engine health\n" * 10, encoding="utf-8")
    second.write_text("beta gradient descent optimizer\n" * 10, encoding="utf-8")
    index.add_documents([str(first), str(second)])

    hits = index.search("gradient descent", top_k=3)

    assert len(hits) >= 1
    assert hits[0].document_path == str(second)
    index.close()


def test_fts_index_empty_query_returns_empty():
    index = FtsIndex()

    assert index.search("") == []
    assert index.search("   ") == []
    assert index.search("nothing", top_k=0) == []
    index.close()


def test_fts_index_stats(tmp_path):
    index = FtsIndex(index_id="fts-stats-test")
    file_path = tmp_path / "doc.txt"
    file_path.write_text("hello world\n" * 5, encoding="utf-8")
    index.add_documents([str(file_path)])

    stats = index.stats()
    assert stats["index_id"] == "fts-stats-test"
    assert stats["document_count"] == 1
    assert stats["chunk_count"] >= 1
    index.close()


def test_fts_index_build_manifest(tmp_path):
    index = FtsIndex(index_id="fts-manifest-test")
    file_path = tmp_path / "code.py"
    file_path.write_text("def hello():\n    return 'world'\n" * 10, encoding="utf-8")
    index.add_documents([str(file_path)])

    manifest = index.build_manifest()
    assert manifest.index_id == "fts-manifest-test"
    assert manifest.document_count == 1
    assert manifest.chunk_count >= 1
    index.close()


def test_fts_index_add_nonexistent_file():
    index = FtsIndex()

    count = index.add_documents(["/nonexistent/path.txt"])
    assert count == 0
    index.close()


def test_fts_index_multiple_searches(tmp_path):
    index = FtsIndex(index_id="fts-multi-test", max_chars=200)
    file_path = tmp_path / "doc.txt"
    file_path.write_text(
        "python is a programming language\n"
        "javascript is also a programming language\n"
        "rust is a systems programming language\n" * 5,
        encoding="utf-8",
    )
    index.add_documents([str(file_path)])

    hits1 = index.search("python", top_k=3)
    hits2 = index.search("javascript", top_k=3)
    hits3 = index.search("rust", top_k=3)

    assert len(hits1) >= 1
    assert len(hits2) >= 1
    assert len(hits3) >= 1
    index.close()
