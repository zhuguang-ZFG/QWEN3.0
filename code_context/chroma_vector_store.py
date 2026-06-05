"""Persistent vector store backed by ChromaDB for semantic code search.

Stores file content chunks with embeddings for similarity search.
Falls back gracefully when ChromaDB is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from code_context.index_store import FileRecord, InMemoryCodeIndex

_log = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "lima_index"
_CHROMADB_AVAILABLE: bool | None = None


def _is_chromadb_available() -> bool:
    global _CHROMADB_AVAILABLE
    if _CHROMADB_AVAILABLE is not None:
        return _CHROMADB_AVAILABLE
    try:
        import chromadb
        _CHROMADB_AVAILABLE = True
    except ImportError:
        _CHROMADB_AVAILABLE = False
        _log.debug("chromadb not installed, using in-memory fallback")
    return _CHROMADB_AVAILABLE


class ChromaCodeIndex:
    """ChromaDB-backed persistent code index with graceful degradation.

    Stores file records with content for vector similarity search.
    Falls back to InMemoryCodeIndex when ChromaDB is unavailable.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = _DEFAULT_COLLECTION,
    ) -> None:
        self._persist_dir = persist_directory or os.environ.get(
            "LIMA_DATA_DIR", ".lima-data",
        )
        self._collection_name = collection_name
        self._chroma_client = None
        self._collection = None
        self._fallback = InMemoryCodeIndex()
        self._use_chroma = _is_chromadb_available()

        if self._use_chroma:
            self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import chromadb

            persist_path = Path(self._persist_dir) / "chroma_db"
            persist_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(persist_path))
            self._collection = self._chroma_client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            _log.info(
                "ChromaDB initialized: %s (%d docs)",
                self._persist_dir,
                self._collection.count(),
            )
        except Exception as exc:
            _log.warning("ChromaDB init failed, using in-memory fallback: %s", exc)
            self._use_chroma = False

    def upsert_file(
        self,
        path: str,
        symbols: list,
        imports: list,
        mtime: float,
        content: str = "",
    ) -> None:
        self._fallback.upsert_file(path, symbols, imports, mtime)
        if not self._use_chroma or not self._collection:
            return
        try:
            doc_id = hashlib.sha256(path.encode()).hexdigest()[:16]
            symbol_text = " ".join(s.name for s in symbols)
            import_text = " ".join(name for name, _line in imports)
            full_text = f"{path} {symbol_text} {import_text}"
            if content:
                full_text = f"{full_text} {content[:2000]}"
            self._collection.upsert(
                ids=[doc_id],
                documents=[full_text],
                metadatas=[{
                    "path": path,
                    "mtime": str(mtime),
                    "symbol_count": str(len(symbols)),
                }],
            )
        except Exception as exc:
            _log.debug("ChromaDB upsert failed for %s: %s", path, exc)

    def search(self, query: str, limit: int = 5) -> list[FileRecord]:
        if not self._use_chroma or not self._collection:
            return self._fallback.search(query, limit)
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(limit, 10),
            )
            records: list[FileRecord] = []
            if results and results.get("metadatas"):
                for meta in results["metadatas"][0]:
                    path = meta.get("path", "")
                    record = self._fallback._files.get(path)
                    if record:
                        records.append(record)
            return records
        except Exception as exc:
            _log.debug("ChromaDB search failed: %s", exc)
            return self._fallback.search(query, limit)

    def delete_file(self, path: str) -> None:
        if path in self._fallback._files:
            del self._fallback._files[path]
        if not self._use_chroma or not self._collection:
            return
        try:
            doc_id = hashlib.sha256(path.encode()).hexdigest()[:16]
            self._collection.delete(ids=[doc_id])
        except Exception:
            pass

    @property
    def count(self) -> int:
        if self._use_chroma and self._collection:
            try:
                return self._collection.count()
            except Exception:
                pass
        return len(self._fallback._files)
