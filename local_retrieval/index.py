"""Local retrieval index interfaces and a toy in-memory token index.

The toy index uses token frequency scoring without embedding models. Its job is
to validate the adapter contract, not to be a production retrieval engine.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

from local_retrieval.chunking import TextChunk
from local_retrieval.manifest import (
    ChunkRecord,
    IndexBackendKind,
    IndexManifest,
    IndexedDocument,
    _make_content_hash,
    redact_text,
)


@dataclass
class RetrievalHit:
    chunk_id: str
    document_path: str
    score: float
    reason: str = ""
    snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "chunk_id": redact_text(self.chunk_id),
            "document_path": redact_text(os.path.basename(self.document_path)),
            "score": self.score,
            "reason": redact_text(self.reason),
            "snippet": redact_text(self.snippet),
        }


class LocalRetrievalIndex(ABC):
    """Abstract local retrieval interface."""

    @abstractmethod
    def add_documents(self, paths: list[str]) -> int: ...

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]: ...

    @abstractmethod
    def stats(self) -> dict: ...

    @abstractmethod
    def build_manifest(self) -> IndexManifest: ...


class InMemoryTokenIndex(LocalRetrievalIndex):
    """Toy index using word frequency scoring. No embeddings."""

    def __init__(self, index_id: str = "", max_chars: int = 2000):
        self.index_id = index_id or f"token-index-{int(time.time())}"
        self._max_chars = max_chars
        self._chunks: list[TextChunk] = []
        self._documents: list[IndexedDocument] = []
        self._source_root = ""

    def add_documents(self, paths: list[str]) -> int:
        from local_retrieval.chunking import SimpleTextChunker

        chunker = SimpleTextChunker(max_chars=self._max_chars)
        count = 0
        existing_paths = []

        for path in paths:
            try:
                with open(path, encoding="utf-8") as file:
                    content = file.read()
            except (OSError, UnicodeDecodeError):
                continue

            chunks = chunker.chunk(content, path)
            chunk_records = [
                ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    document_path=path,
                    chunk_index=int(chunk.metadata.get("chunk_index", index)),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    char_offset=chunk.char_offset,
                    char_length=chunk.char_length,
                    content_hash=_make_content_hash(chunk.text),
                )
                for index, chunk in enumerate(chunks)
            ]
            self._documents.append(
                IndexedDocument(
                    path=path,
                    file_hash=_make_content_hash(content),
                    file_size_bytes=len(content.encode()),
                    mtime=os.path.getmtime(path),
                    language=_guess_language(path),
                    chunks=chunk_records,
                )
            )
            self._chunks.extend(chunks)
            existing_paths.append(path)
            count += 1

        if not self._source_root and existing_paths:
            self._source_root = os.path.commonpath([os.path.abspath(path) for path in existing_paths])
            if os.path.isfile(self._source_root):
                self._source_root = os.path.dirname(self._source_root)

        return count

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        if not self._chunks or top_k <= 0:
            return []

        query_terms = _tokenize(query)
        if not query_terms:
            return []

        scored: list[tuple[float, str, TextChunk, list[str]]] = []
        query_counts = Counter(query_terms)
        unique_terms = set(query_terms)

        for chunk in self._chunks:
            chunk_terms = _tokenize(chunk.text)
            if not chunk_terms:
                continue
            chunk_counts = Counter(chunk_terms)
            matched_terms = sorted(term for term in unique_terms if chunk_counts[term])
            if not matched_terms:
                continue

            weighted_matches = sum(min(query_counts[term], chunk_counts[term]) for term in matched_terms)
            score = weighted_matches / max(1, len(query_terms))
            scored.append((score, chunk.chunk_id, chunk, matched_terms))

        scored.sort(key=lambda item: (-item[0], item[1]))
        hits = []
        for score, _, chunk, matched_terms in scored[:top_k]:
            reason = f"matched: {', '.join(matched_terms[:3])}; chunk_lines: {chunk.start_line}-{chunk.end_line}"
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    document_path=str(chunk.metadata.get("path", "")),
                    score=round(score, 4),
                    reason=redact_text(reason),
                    snippet=redact_text(chunk.text[:150].replace("\n", " ")),
                )
            )
        return hits

    def stats(self) -> dict:
        return {
            "index_id": self.index_id,
            "backend": IndexBackendKind.IN_MEMORY_TOKEN.value,
            "document_count": len(self._documents),
            "chunk_count": len(self._chunks),
            "max_chars_per_chunk": self._max_chars,
            "total_chars": sum(chunk.char_length for chunk in self._chunks),
        }

    def build_manifest(self) -> IndexManifest:
        return IndexManifest(
            index_id=self.index_id,
            backend_kind=IndexBackendKind.IN_MEMORY_TOKEN,
            source_root=self._source_root,
            storage_bytes=sum(document.file_size_bytes for document in self._documents),
            documents=list(self._documents),
        )


def _guess_language(path: str) -> str:
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    return {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "rs": "rust",
        "go": "go",
        "md": "markdown",
    }.get(ext, "")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())
