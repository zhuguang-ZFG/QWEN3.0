"""Tests for M16 local retrieval index lab."""

import os

import pytest

from local_retrieval.chunking import CodeAwareChunker, SimpleTextChunker
from local_retrieval.eval_bridge import evaluate_index, format_eval_report, make_eval_query
from local_retrieval.index import InMemoryTokenIndex, RetrievalHit
from local_retrieval.leann_adapter import (
    LeannAdapterConfig,
    create_leann_index,
    is_leann_available,
    leann_status,
)
from local_retrieval.manifest import (
    ChunkRecord,
    IndexBackendKind,
    IndexManifest,
    IndexedDocument,
    _make_chunk_id,
    _make_content_hash,
    _redact_path,
)


def test_chunk_record_to_dict_redacts_paths_and_secret_metadata():
    chunk = ChunkRecord(
        chunk_id="c1",
        document_path="/home/user/project/file.py",
        chunk_index=0,
        start_line=1,
        end_line=10,
        char_offset=0,
        char_length=500,
        content_hash="abc123",
        metadata={"api_key": "sk-secret-value", "safe": "ok"},
    )

    data = chunk.to_dict()

    assert data["chunk_id"] == "c1"
    assert data["document_path"] == "file.py"
    assert "/home/user" not in data["document_path"]
    assert "[REDACTED]" in data["metadata"]
    assert data["metadata"]["safe"] == "ok"


def test_chunk_record_round_trip():
    chunk = ChunkRecord(
        chunk_id="c1",
        document_path="file.py",
        chunk_index=2,
        start_line=3,
        end_line=5,
        content_hash="hash",
    )

    restored = ChunkRecord.from_dict(chunk.to_dict())

    assert restored.chunk_id == "c1"
    assert restored.chunk_index == 2
    assert restored.start_line == 3


def test_index_manifest_to_dict_and_from_dict_round_trips_chunks():
    chunk = ChunkRecord(
        chunk_id="chunk-a",
        document_path="/home/user/project/a.py",
        chunk_index=0,
        content_hash="hchunk",
    )
    manifest = IndexManifest(
        index_id="idx-1",
        backend_kind=IndexBackendKind.IN_MEMORY_TOKEN,
        source_root="/home/user/project",
        embedding_model="none",
        build_config={"token": "secret", "safe": "ok"},
        evidence_refs=["Bearer token-string-here"],
        documents=[IndexedDocument(
            path="/home/user/project/a.py",
            file_hash="h1",
            file_size_bytes=100,
            chunks=[chunk],
        )],
    )

    data = manifest.to_dict()
    restored = IndexManifest.from_dict(data)

    assert data["index_id"] == "idx-1"
    assert data["source_root"] == "project"
    assert data["build_config"]["[REDACTED]"] == "[REDACTED]"
    assert data["evidence_refs"] == ["[REDACTED]"]
    assert restored.document_count == 1
    assert restored.chunk_count == 1
    assert restored.documents[0].chunks[0].chunk_id == "chunk-a"


def test_manifest_from_dict_unknown_backend_defaults_to_token():
    manifest = IndexManifest.from_dict({
        "index_id": "idx",
        "backend_kind": "unknown",
        "documents": [],
    })

    assert manifest.backend_kind is IndexBackendKind.IN_MEMORY_TOKEN


def test_manifest_redacts_secret_like_paths():
    assert _redact_path("/tmp/sk-secret-file.py") == "[REDACTED]"


def test_chunk_id_stable():
    id1 = _make_chunk_id("/a/b.py", 3)
    id2 = _make_chunk_id("/a/b.py", 3)
    id3 = _make_chunk_id("/a/b.py", 4)

    assert id1 == id2
    assert id1 != id3


def test_content_hash_deterministic():
    assert _make_content_hash("hello") == _make_content_hash("hello")


def test_simple_chunker_produces_stable_chunks_with_metadata():
    chunker = SimpleTextChunker(max_chars=500, overlap_lines=1)
    text = "\n".join(f"line {i}: some content here" for i in range(50))

    chunks1 = chunker.chunk(text, "test.txt")
    chunks2 = chunker.chunk(text, "test.txt")

    assert len(chunks1) >= 2
    assert [chunk.chunk_id for chunk in chunks1] == [chunk.chunk_id for chunk in chunks2]
    assert chunks1[0].metadata["path"] == "test.txt"
    assert chunks1[0].metadata["chunk_index"] == 0


def test_simple_chunker_empty_text():
    chunker = SimpleTextChunker()

    assert chunker.chunk("", "test.txt") == []
    assert chunker.chunk("   \n  ", "test.txt") == []


def test_simple_chunker_overlap_advances_and_repeats_lines():
    chunker = SimpleTextChunker(max_chars=30, overlap_lines=1)
    text = "\n".join(f"line {i}" for i in range(10))

    chunks = chunker.chunk(text, "test.txt")

    assert len(chunks) > 1
    assert chunks[1].start_line <= chunks[0].end_line


def test_simple_chunker_clamps_bad_config():
    chunker = SimpleTextChunker(max_chars=0, overlap_lines=-5)

    chunks = chunker.chunk("abc", "tiny.txt")

    assert len(chunks) == 1


def test_code_aware_chunker_delegates():
    chunker = CodeAwareChunker(max_chars=500)
    text = "\n".join(f"code line {i}" for i in range(30))

    chunks = chunker.chunk(text, "test.py")

    assert len(chunks) >= 1


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


def test_eval_bridge_with_toy_index_uses_chunk_ids(tmp_path):
    index = InMemoryTokenIndex(index_id="eval-test")
    file_path = tmp_path / "doc_0.txt"
    file_path.write_text(
        "python routing engine selects backends based on health scores",
        encoding="utf-8",
    )
    index.add_documents([str(file_path)])
    expected_chunk = index.search("routing engine health", top_k=1)[0].chunk_id

    queries = [make_eval_query("routing engine health", [expected_chunk])]
    summary = evaluate_index(index, queries, top_k=5)

    assert summary.queries == 1
    assert summary.mean_recall == 1.0
    assert summary.hit_rate == 1.0
    assert summary.mean_mrr == 1.0
    assert "Recall" in format_eval_report(summary)


def test_eval_bridge_empty_queries():
    index = InMemoryTokenIndex(index_id="eval-empty")

    summary = evaluate_index(index, [], top_k=5)

    assert summary.queries == 0
    assert summary.mean_recall == 0.0


def test_make_eval_query():
    query = make_eval_query("test query", ["a.py", "b.py"], "test description")

    assert query.query == "test query"
    assert query.expected_paths == ["a.py", "b.py"]


def test_is_leann_available_default_false(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert is_leann_available() is False


def test_leann_status_reports_unavailable(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    status = leann_status()

    assert status["available"] is False
    assert status["env_gate"] is False
    assert "note" in status


def test_create_leann_index_returns_none_when_unavailable(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert create_leann_index() is None


def test_leann_adapter_config_defaults_and_to_dict():
    config = LeannAdapterConfig()

    assert config.embedding_model == "all-MiniLM-L6-v2"
    assert config.dim == 384
    assert config.use_gpu is False
    assert config.metric == "cosine"
    assert config.to_dict()["batch_size"] == 32


def test_leann_not_importable_without_env(monkeypatch):
    monkeypatch.delenv("LIMA_ENABLE_LEANN", raising=False)

    assert is_leann_available() is False
