"""Metadata-only manifest for local retrieval indexes.

The manifest never stores full document text. It records paths, hashes, chunk
ids, and small metadata fields with secret-like values redacted.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_REDACTED = "[REDACTED]"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "cookie",
    "credential",
    "password",
    "secret",
    "sk-",
    "token=",
)


class IndexBackendKind(str, Enum):
    IN_MEMORY_TOKEN = "in_memory_token"
    IN_MEMORY_EMBEDDING = "in_memory_embedding"
    LEANN = "leann"
    FAISS = "faiss"


@dataclass
class ChunkRecord:
    chunk_id: str
    document_path: str
    chunk_index: int
    start_line: int = 0
    end_line: int = 0
    char_offset: int = 0
    char_length: int = 0
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": redact_text(self.chunk_id),
            "document_path": _redact_path(self.document_path),
            "chunk_index": self.chunk_index,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "char_offset": self.char_offset,
            "char_length": self.char_length,
            "content_hash": redact_text(self.content_hash),
            "metadata": _redact_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkRecord":
        return cls(
            chunk_id=str(data.get("chunk_id", "")),
            document_path=str(data.get("document_path", "")),
            chunk_index=_safe_int(data.get("chunk_index", 0)),
            start_line=_safe_int(data.get("start_line", 0)),
            end_line=_safe_int(data.get("end_line", 0)),
            char_offset=_safe_int(data.get("char_offset", 0)),
            char_length=_safe_int(data.get("char_length", 0)),
            content_hash=str(data.get("content_hash", "")),
            metadata=_dict_or_empty(data.get("metadata")),
        )


@dataclass
class IndexedDocument:
    path: str
    file_hash: str = ""
    file_size_bytes: int = 0
    mtime: float = 0.0
    chunk_count: int = 0
    language: str = ""
    chunks: list[ChunkRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.chunks:
            self.chunk_count = len(self.chunks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": _redact_path(self.path),
            "file_hash": redact_text(self.file_hash),
            "file_size_bytes": self.file_size_bytes,
            "mtime": self.mtime,
            "chunk_count": self.chunk_count,
            "language": redact_text(self.language),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexedDocument":
        chunks = [
            ChunkRecord.from_dict(item)
            for item in data.get("chunks", [])
            if isinstance(item, dict)
        ]
        return cls(
            path=str(data.get("path", "")),
            file_hash=str(data.get("file_hash", "")),
            file_size_bytes=_safe_int(data.get("file_size_bytes", 0)),
            mtime=float(data.get("mtime", 0.0) or 0.0),
            chunk_count=_safe_int(data.get("chunk_count", len(chunks))),
            language=str(data.get("language", "")),
            chunks=chunks,
        )


@dataclass
class IndexManifest:
    index_id: str
    backend_kind: IndexBackendKind
    source_root: str = ""
    created_at: float = field(default_factory=time.time)
    document_count: int = 0
    chunk_count: int = 0
    embedding_model: str = ""
    storage_bytes: int = 0
    build_config: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    documents: list[IndexedDocument] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.document_count = len(self.documents)
        self.chunk_count = sum(document.chunk_count for document in self.documents)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_id": redact_text(self.index_id),
            "backend_kind": self.backend_kind.value,
            "source_root": _redact_path(self.source_root),
            "created_at": self.created_at,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "embedding_model": redact_text(self.embedding_model),
            "storage_bytes": self.storage_bytes,
            "build_config": _redact_metadata(self.build_config),
            "evidence_refs": [redact_text(ref) for ref in self.evidence_refs],
            "documents": [document.to_dict() for document in self.documents],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexManifest":
        documents = [
            IndexedDocument.from_dict(item)
            for item in data.get("documents", [])
            if isinstance(item, dict)
        ]
        return cls(
            index_id=str(data.get("index_id", "")),
            backend_kind=_parse_backend_kind(data.get("backend_kind")),
            source_root=str(data.get("source_root", "")),
            created_at=float(data.get("created_at", time.time()) or 0.0),
            embedding_model=str(data.get("embedding_model", "")),
            storage_bytes=_safe_int(data.get("storage_bytes", 0)),
            build_config=_dict_or_empty(data.get("build_config")),
            evidence_refs=_string_list(data.get("evidence_refs")),
            documents=documents,
        )


def _make_chunk_id(file_path: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{file_path}:{chunk_index}".encode()).hexdigest()[:16]
    return f"chunk-{digest}"


def _make_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _redact_path(path: str) -> str:
    if not path:
        return ""
    return redact_text(os.path.basename(path))


def redact_text(value: object) -> str:
    text = str(value)
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return _REDACTED
    try:
        from session_memory.redact import sanitize_for_display
        return sanitize_for_display(text)
    except ImportError:
        return text


def _redact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        safe_key = _REDACTED if _looks_secret_key(key_text) else redact_text(key_text)
        redacted[safe_key] = _redact_value(value)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_metadata(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _parse_backend_kind(value: Any) -> IndexBackendKind:
    try:
        return IndexBackendKind(str(value))
    except ValueError:
        return IndexBackendKind.IN_MEMORY_TOKEN


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _looks_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker.strip(" =") in lowered for marker in _SECRET_MARKERS)
