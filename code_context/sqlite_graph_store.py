"""Persistent graph index backed by SQLite with FTS5.

Stores code relationships (imports, calls, extends, defines) with bidirectional
edges and full-text search on entity names. Survives process restarts.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

from code_context.graph_index import GraphIndex, GraphRelation, GraphSearchResult
from config.db_config import LIMA_DATA_DIR as _DEFAULT_DB_DIR

_log = logging.getLogger(__name__)


class SqliteGraphIndex(GraphIndex):
    """SQLite-backed persistent graph with FTS5 full-text search.

    Thread safety: uses a per-instance RLock to protect all database access
    because the connection is shared across threads (check_same_thread=False).
    """

    def __init__(self, db_path: str | None = None) -> None:
        resolved = db_path or str(Path(_DEFAULT_DB_DIR) / "code_graph.db")
        Path(resolved).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = resolved
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(resolved, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
                CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation_type);
            """)
            try:
                self._conn.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS edges_fts USING fts5(
                        source, target, relation_type,
                        content=edges, content_rowid=id
                    );
                    CREATE TRIGGER IF NOT EXISTS edges_ai AFTER INSERT ON edges BEGIN
                        INSERT INTO edges_fts(rowid, source, target, relation_type)
                        VALUES (new.id, new.source, new.target, new.relation_type);
                    END;
                    CREATE TRIGGER IF NOT EXISTS edges_ad AFTER DELETE ON edges BEGIN
                        INSERT INTO edges_fts(edges_fts, rowid, source, target, relation_type)
                        VALUES ('delete', old.id, old.source, old.target, old.relation_type);
                    END;
                """)
            except Exception as exc:
                _log.warning("FTS5 trigger setup skipped for %s: %s", self._db_path, exc)

    def add_relation(self, source: str, target: str, relation_type: str) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO edges (source, target, relation_type, weight, created_at) VALUES (?, ?, ?, 1.0, ?)",
                (source, target, relation_type, now),
            )
            self._conn.execute(
                "INSERT INTO edges (source, target, relation_type, weight, created_at) VALUES (?, ?, ?, 0.5, ?)",
                (target, source, f"rev_{relation_type}", now),
            )
            self._conn.commit()

    def delete_file(self, path: str) -> None:
        """Remove all edges whose source or target equals *path*."""
        with self._lock:
            self._conn.execute("DELETE FROM edges WHERE source = ? OR target = ?", (path, path))
            self._conn.commit()

    def add_file_relations(
        self,
        filename: str,
        relations: list[GraphRelation],
    ) -> int:
        now = time.time()
        count = 0
        with self._lock:
            for rel in relations:
                self._conn.execute(
                    "INSERT INTO edges (source, target, relation_type, weight, created_at) VALUES (?, ?, ?, ?, ?)",
                    (rel.source, rel.target, rel.relation_type, rel.weight, now),
                )
                self._conn.execute(
                    "INSERT INTO edges (source, target, relation_type, weight, created_at) VALUES (?, ?, ?, ?, ?)",
                    (rel.target, rel.source, f"rev_{rel.relation_type}", rel.weight * 0.5, now),
                )
                count += 1
            self._conn.commit()
        return count

    def get_related(self, entity: str, max_depth: int = 2) -> list[GraphRelation]:
        visited: set[str] = set()
        results: list[GraphRelation] = []
        queue: list[tuple[str, int]] = [(entity, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            with self._lock:
                rows = self._conn.execute(
                    "SELECT source, target, relation_type, weight FROM edges WHERE source = ?",
                    (current,),
                ).fetchall()
            for src, tgt, rel_type, weight in rows:
                results.append(GraphRelation(source=src, target=tgt, relation_type=rel_type, weight=weight))
                if depth + 1 <= max_depth:
                    queue.append((tgt, depth + 1))
        return results

    def search(
        self,
        entities: list[str],
        max_depth: int = 2,
        max_results: int = 10,
    ) -> list[GraphSearchResult]:
        seen: dict[str, GraphSearchResult] = {}
        for entity in entities:
            for rel in self.get_related(entity, max_depth=max_depth):
                path = rel.target
                if path in seen:
                    seen[path].score += 0.3
                    seen[path].source = "both"
                    seen[path].relations.append(f"{rel.relation_type}:{rel.source}")
                else:
                    seen[path] = GraphSearchResult(
                        entity=path,
                        score=0.5,
                        relations=[f"{rel.relation_type}:{rel.source}"],
                    )
        ranked = sorted(seen.values(), key=lambda r: -r.score)
        return ranked[:max_results]

    def fts_search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT source, target, relation_type, rank FROM edges_fts "
                    "WHERE edges_fts MATCH ? ORDER BY rank LIMIT ?",
                    (query, limit),
                ).fetchall()
            return [{"source": r[0], "target": r[1], "relation_type": r[2], "rank": r[3]} for r in rows]
        except Exception as exc:
            _log.warning("sqlite graph fts_search failed: %s", exc)
            return []

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM edges")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @property
    def edge_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()
            return row[0] if row else 0

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception as exc:
            _log.warning("sqlite_graph_store cleanup failed: %s", exc)
