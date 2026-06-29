"""SQLite-backed store for semantic cache entries."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

from config.sqlite_pool import pooled_sqlite_conn
from semantic_cache.config import cache_db_path


@dataclass(frozen=True)
class CacheEntry:
    id: int
    query_text: str
    embedding: list[float]
    response: str
    created_at: float


class SemanticCacheStore:
    """SQLite store for query/response pairs with embedding vectors."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS semantic_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_hash TEXT NOT NULL,
        query_text TEXT NOT NULL,
        embedding TEXT NOT NULL,
        response TEXT NOT NULL,
        created_at REAL NOT NULL,
        hit_count INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_semantic_cache_created_at
        ON semantic_cache(created_at);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_cache_query_hash
        ON semantic_cache(query_hash);
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or cache_db_path()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with pooled_sqlite_conn(self.db_path) as conn:
            # AUDIT-8-P3：启用 WAL 模式，允许并发读写（缓存查询时不阻塞写入），
            # 消除默认 journal 模式下 upsert/bump_hit_count 与 lookup 的全库互斥锁。
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(self._SCHEMA)

    def get_candidates(
        self,
        min_created_at: float,
        limit: int = 100,
    ) -> list[CacheEntry]:
        """Return recent entries that may match the query."""
        with pooled_sqlite_conn(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, query_text, embedding, response, created_at
                FROM semantic_cache
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (min_created_at, limit),
            ).fetchall()
        return [
            CacheEntry(
                id=row["id"],
                query_text=row["query_text"],
                embedding=json.loads(row["embedding"]),
                response=row["response"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def upsert(
        self,
        query_hash: str,
        query_text: str,
        embedding: list[float],
        response: str,
    ) -> None:
        """Insert or replace a cache entry keyed by query hash."""
        now = time.time()
        with pooled_sqlite_conn(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO semantic_cache (query_hash, query_text, embedding, response, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(query_hash) DO UPDATE SET
                    query_text=excluded.query_text,
                    embedding=excluded.embedding,
                    response=excluded.response,
                    created_at=excluded.created_at,
                    hit_count=0
                """,
                (
                    query_hash,
                    query_text,
                    json.dumps(embedding),
                    response,
                    now,
                ),
            )

    def bump_hit_count(self, entry_id: int) -> None:
        """Increment hit count for a returned entry."""
        with pooled_sqlite_conn(self.db_path) as conn:
            conn.execute(
                "UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE id = ?",
                (entry_id,),
            )

    def clear(self) -> int:
        """Delete all cached entries. Returns deleted count."""
        with pooled_sqlite_conn(self.db_path) as conn:
            cur = conn.execute("DELETE FROM semantic_cache")
            return cur.rowcount

    def prune(self, max_age_seconds: float) -> int:
        """Delete entries older than ``max_age_seconds``. Returns deleted count."""
        cutoff = time.time() - max_age_seconds
        with pooled_sqlite_conn(self.db_path) as conn:
            cur = conn.execute("DELETE FROM semantic_cache WHERE created_at < ?", (cutoff,))
            return cur.rowcount
