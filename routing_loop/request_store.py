"""Persistent request log — stores every request's features + outcome for ML training.

SQLite-backed, append-only. This is the single source of truth for the
closed-loop feedback system: request → route → execute → log → train → better route.
"""

from __future__ import annotations

import logging
import os
import pickle
import sqlite3
import time
from dataclasses import dataclass

_log = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.environ.get(
    "LIMA_REQUEST_LOG_DB", "data/request_log.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS request_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    request_id TEXT,
    scenario TEXT DEFAULT '',
    message_length INTEGER DEFAULT 0,
    code_ratio REAL DEFAULT 0.0,
    chinese_ratio REAL DEFAULT 0.0,
    feature_vector BLOB,
    backend TEXT DEFAULT '',
    success INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0.0,
    quality_score REAL DEFAULT 0.0,
    fallback_used INTEGER DEFAULT 0,
    error_class TEXT DEFAULT '',
    tokens_prompt INTEGER DEFAULT 0,
    tokens_completion INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rl_timestamp ON request_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_rl_backend ON request_log(backend);
CREATE INDEX IF NOT EXISTS idx_rl_scenario ON request_log(scenario);
CREATE INDEX IF NOT EXISTS idx_rl_success ON request_log(success);
"""


@dataclass
class RequestRecord:
    id: int = 0
    timestamp: float = 0.0
    request_id: str = ""
    scenario: str = ""
    message_length: int = 0
    code_ratio: float = 0.0
    chinese_ratio: float = 0.0
    feature_vector: list[float] | None = None
    backend: str = ""
    success: bool = False
    latency_ms: float = 0.0
    quality_score: float = 0.0
    fallback_used: bool = False
    error_class: str = ""
    tokens_prompt: int = 0
    tokens_completion: int = 0


class RequestStore:
    """SQLite-backed append-only request log for ML training data."""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self._db_path, timeout=5)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
        return self._conn

    def log_request(
        self,
        request_id: str = "",
        scenario: str = "",
        message_length: int = 0,
        code_ratio: float = 0.0,
        chinese_ratio: float = 0.0,
        feature_vector: list[float] | None = None,
        backend: str = "",
        success: bool = False,
        latency_ms: float = 0.0,
        quality_score: float = 0.0,
        fallback_used: bool = False,
        error_class: str = "",
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
    ) -> None:
        """Append one request record to the log."""
        try:
            fv_blob = pickle.dumps(feature_vector) if feature_vector else None
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO request_log
                   (timestamp, request_id, scenario, message_length, code_ratio,
                    chinese_ratio, feature_vector, backend, success, latency_ms,
                    quality_score, fallback_used, error_class, tokens_prompt, tokens_completion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    time.time(), request_id, scenario, message_length,
                    code_ratio, chinese_ratio, fv_blob, backend,
                    1 if success else 0, latency_ms, quality_score,
                    1 if fallback_used else 0, error_class,
                    tokens_prompt, tokens_completion,
                ),
            )
            conn.commit()
        except Exception as exc:
            _log.debug("request_store.log_request failed: %s", exc)

    def get_training_data(
        self, since_hours: int = 168, min_backend: str = ""
    ) -> list[RequestRecord]:
        """Read recent requests for ML training (default: last 7 days)."""
        cutoff = time.time() - (since_hours * 3600)
        conn = self._get_conn()
        query = "SELECT * FROM request_log WHERE timestamp > ?"
        params: list = [cutoff]
        if min_backend:
            query += " AND backend = ?"
            params.append(min_backend)
        query += " ORDER BY timestamp DESC"

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_backend_stats(self, backend: str, scenario: str = "") -> dict:
        """Get aggregated stats for a backend (optionally filtered by scenario)."""
        conn = self._get_conn()
        where = "backend = ?"
        params: list = [backend]
        if scenario:
            where += " AND scenario = ?"
            params.append(scenario)

        row = conn.execute(
            f"SELECT COUNT(*), SUM(success), AVG(latency_ms), AVG(quality_score) "
            f"FROM request_log WHERE {where}",
            params,
        ).fetchone()

        total = row[0] or 0
        successes = row[1] or 0
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_latency_ms": row[2] or 0.0,
            "avg_quality": row[3] or 0.0,
        }

    def get_recent_features(self, n: int = 100) -> list[RequestRecord]:
        """Read last N requests with feature vectors for incremental training."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM request_log WHERE feature_vector IS NOT NULL "
            "ORDER BY timestamp DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        """Total records in the log."""
        return self._get_conn().execute("SELECT COUNT(*) FROM request_log").fetchone()[0]

    def _row_to_record(self, row: tuple) -> RequestRecord:
        fv = None
        if row[7]:  # feature_vector column
            try:
                fv = pickle.loads(row[7])
            except Exception as exc:
                _log.debug("routing_loop/request_store.py: {}", type(exc).__name__)
        return RequestRecord(
            id=row[0], timestamp=row[1], request_id=row[2] or "",
            scenario=row[3] or "", message_length=row[4] or 0,
            code_ratio=row[5] or 0.0, chinese_ratio=row[6] or 0.0,
            feature_vector=fv, backend=row[8] or "",
            success=bool(row[9]), latency_ms=row[10] or 0.0,
            quality_score=row[11] or 0.0, fallback_used=bool(row[12]),
            error_class=row[13] or "", tokens_prompt=row[14] or 0,
            tokens_completion=row[15] or 0,
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


_store: RequestStore | None = None


def get_request_store() -> RequestStore:
    global _store
    if _store is None:
        _store = RequestStore()
    return _store
