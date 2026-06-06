"""ChromaDB-backed persistent memory store for session_memory.

Provides semantic search via ChromaDB's DefaultEmbeddingFunction
(all-MiniLM-L6-v2, 384-dim, local, zero API dependency).

Falls back gracefully when chromadb is unavailable — callers should
check available() before using and degrade to Jina + SQLite cosine.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

# Patch sqlite3 for older Linux distros (ChromaDB requires >= 3.35.0)
try:
    __import__("pysqlite3")
    import sys as _sys
    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except ImportError:
    pass

_log = logging.getLogger(__name__)

_COLLECTION_NAME = "lima_memory"
_INITIALIZED: bool | None = None
_client = None
_collection = None


def _is_chromadb_available() -> bool:
    """Check if chromadb package is importable."""
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


def available() -> bool:
    """Check if ChromaDB memory store is initialized and ready."""
    global _INITIALIZED
    if _INITIALIZED is not None:
        return _INITIALIZED
    if not _is_chromadb_available():
        _INITIALIZED = False
        return False
    _init_store()
    return bool(_INITIALIZED)


def _data_dir() -> Path:
    return Path(os.environ.get("LIMA_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


def _init_store() -> None:
    """Initialize ChromaDB client and collection. Idempotent."""
    global _INITIALIZED, _client, _collection
    if _INITIALIZED is not None:
        return

    try:
        from chromadb import PersistentClient
        from chromadb.utils import embedding_functions

        persist_path = _data_dir() / "chroma_memory"
        persist_path.mkdir(parents=True, exist_ok=True)

        _client = PersistentClient(path=str(persist_path))
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        _INITIALIZED = True
        count = _collection.count()
        _log.info("ChromaDB memory store ready: %s (%d docs)", persist_path, count)
    except Exception as exc:
        _log.warning("ChromaDB memory store unavailable: %s", exc)
        _INITIALIZED = False
        _client = None
        _collection = None


def add_memory(
    sqlite_id: int,
    session_id: str,
    summary: str,
    memory_type: str = "exchange",
    timestamp: float | None = None,
) -> bool:
    """Add a memory to ChromaDB. Returns True on success."""
    if not available() or _collection is None:
        return False
    try:
        doc_id = f"mem_{sqlite_id}"
        ts = timestamp or time.time()
        _collection.upsert(
            ids=[doc_id],
            documents=[summary],
            metadatas=[{
                "sqlite_id": str(sqlite_id),
                "session_id": session_id,
                "memory_type": memory_type,
                "timestamp": str(ts),
            }],
        )
        return True
    except Exception as exc:
        _log.debug("ChromaDB add_memory failed for id=%d: %s", sqlite_id, exc)
        return False


def search_memory(
    session_id: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Semantic search against ChromaDB. Returns [{sqlite_id, score, metadata}, ...]."""
    if not available() or _collection is None:
        return []

    try:
        # Query with session filter via where clause
        results = _collection.query(
            query_texts=[query],
            n_results=min(limit, 10),
            where={"session_id": session_id},
        )
        items = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            for i, doc_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                dist = distances[i] if i < len(distances) else 1.0
                # Convert cosine distance (0=identical, 2=opposite) to similarity (1=identical, 0=opposite)
                sim = round(max(0.0, 1.0 - dist / 2.0), 4)
                try:
                    sqlite_id = int(meta.get("sqlite_id", "0"))
                except (ValueError, TypeError):
                    sqlite_id = 0
                items.append({
                    "sqlite_id": sqlite_id,
                    "chroma_id": doc_id,
                    "similarity": sim,
                    "metadata": meta,
                })
        return items
    except Exception as exc:
        _log.debug("ChromaDB search failed: %s", exc)
        return []


def delete_memory(sqlite_id: int) -> bool:
    """Remove a memory from ChromaDB by its SQLite ID."""
    if not available() or _collection is None:
        return False
    try:
        doc_id = f"mem_{sqlite_id}"
        _collection.delete(ids=[doc_id])
        return True
    except Exception:
        return False


def store_stats() -> dict:
    """Return stats about the ChromaDB memory store."""
    if not available() or _collection is None:
        return {"available": False, "count": 0}
    try:
        return {"available": True, "count": _collection.count()}
    except Exception:
        return {"available": False, "count": 0}
