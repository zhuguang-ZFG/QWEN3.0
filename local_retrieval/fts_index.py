"""SQLite FTS5-backed retrieval index.

Replaces the toy InMemoryTokenIndex with stdlib sqlite3 FTS5 for better
ranking (BM25) and lower custom code surface.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

from local_retrieval.chunking import SimpleTextChunker, TextChunk
from local_retrieval.index import LocalRetrievalIndex, RetrievalHit
from local_retrieval.manifest import (
    ChunkRecord,
    IndexBackendKind,
    IndexManifest,
    IndexedDocument,
    _make_content_hash,
    redact_text,
)


class FtsIndex(LocalRetrievalIndex):
    """FTS5-backed index using in-memory sqlite3 database."""

    def __init__(self, index_id: str = "", max_chars: int = 2000):
        self.index_id = index_id or f"fts-index-{int(time.time())}"
        self._max_chars = max_chars
        self._documents: list[IndexedDocument] = []
        self._source_root = ""
        self._conn: sqlite3.Connection | None = None
        self._chunk_count = 0

    def _ensure_db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(":memory:")
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks
                USING fts5(
                    chunk_id,
                    document_path,
                    content,
                    start_line,
                    end_line,
                    chunk_index UNINDEXED
                )
            """)
        return self._conn

    def _index_single_file(self, path: str, conn: sqlite3.Connection, chunker) -> bool:
        """Index one file into FTS5 and document list. Return True on success."""
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return False

        chunks = chunker.chunk(content, path)
        chunk_records = [
            ChunkRecord(
                chunk_id=chunk.chunk_id,
                document_path=path,
                chunk_index=int(chunk.metadata.get("chunk_index", idx)),
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                char_offset=chunk.char_offset,
                char_length=chunk.char_length,
                content_hash=_make_content_hash(chunk.text),
            )
            for idx, chunk in enumerate(chunks)
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

        conn.executemany(
            "INSERT INTO chunks (chunk_id, document_path, content, start_line, end_line, chunk_index) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    chunk.chunk_id,
                    path,
                    chunk.text,
                    chunk.start_line,
                    chunk.end_line,
                    int(chunk.metadata.get("chunk_index", idx)),
                )
                for idx, chunk in enumerate(chunks)
            ],
        )
        self._chunk_count += len(chunks)
        return True

    def add_documents(self, paths: list[str]) -> int:
        conn = self._ensure_db()
        chunker = SimpleTextChunker(max_chars=self._max_chars)
        count = 0
        existing_paths = []

        for path in paths:
            if self._index_single_file(path, conn, chunker):
                existing_paths.append(path)
                count += 1

        conn.commit()

        if not self._source_root and existing_paths:
            self._source_root = os.path.commonpath(
                [os.path.abspath(p) for p in existing_paths]
            )
            if os.path.isfile(self._source_root):
                self._source_root = os.path.dirname(self._source_root)

        return count

    def _execute_fts_query(self, conn, fts_query, terms, top_k):
        """Execute FTS5 MATCH query with LIKE fallback."""
        try:
            return conn.execute(
                """
                SELECT chunk_id, document_path, snippet(chunks, 2, '...', '...', '', 32) as snip,
                       rank, start_line, end_line
                FROM chunks
                WHERE chunks MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, top_k),
            )
        except sqlite3.OperationalError:
            like_patterns = [f"%{term}%" for term in terms]
            conditions = " OR ".join(["content LIKE ?"] * len(terms))
            return conn.execute(
                f"""
                SELECT chunk_id, document_path, substr(content, 1, 150) as snip,
                       0 as rank, start_line, end_line
                FROM chunks
                WHERE {conditions}
                LIMIT ?
                """,
                (*like_patterns, top_k),
            )

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        conn = self._ensure_db()
        if not query.strip() or top_k <= 0:
            return []

        terms = query.strip().split()
        if not terms:
            return []

        fts_query = " OR ".join(terms)
        cursor = self._execute_fts_query(conn, fts_query, terms, top_k)

        hits = []
        for row in cursor.fetchall():
            chunk_id, doc_path, snippet, rank, start_line, end_line = row
            score = round(-rank, 4) if rank != 0 else 1.0
            reason = f"FTS5 BM25; chunk_lines: {start_line}-{end_line}"
            hits.append(
                RetrievalHit(
                    chunk_id=chunk_id,
                    document_path=doc_path,
                    score=score,
                    reason=redact_text(reason),
                    snippet=redact_text(snippet.replace("\n", " ")),
                )
            )

        return hits

    def stats(self) -> dict:
        return {
            "index_id": self.index_id,
            "backend": "fts5",
            "document_count": len(self._documents),
            "chunk_count": self._chunk_count,
            "max_chars_per_chunk": self._max_chars,
            "total_chars": sum(c.char_length for d in self._documents for c in d.chunks),
        }

    def build_manifest(self) -> IndexManifest:
        return IndexManifest(
            index_id=self.index_id,
            backend_kind=IndexBackendKind.IN_MEMORY_TOKEN,  # Keep compatible kind
            source_root=self._source_root,
            storage_bytes=sum(d.file_size_bytes for d in self._documents),
            documents=list(self._documents),
        )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


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
