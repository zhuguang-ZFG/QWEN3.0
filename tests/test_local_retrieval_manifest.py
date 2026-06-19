"""Manifest and redaction tests for the local retrieval lab."""

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
        documents=[
            IndexedDocument(
                path="/home/user/project/a.py",
                file_hash="h1",
                file_size_bytes=100,
                chunks=[chunk],
            )
        ],
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
    manifest = IndexManifest.from_dict(
        {
            "index_id": "idx",
            "backend_kind": "unknown",
            "documents": [],
        }
    )

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
