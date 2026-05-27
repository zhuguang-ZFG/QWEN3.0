"""Unified Event Store — single table for all LiMa outcomes and evidence.

Replaces: outcome_ledger + capability_evidence (merged 2026-05-27).
Every event — chat turn, CI run, device task, worker result, eval report —
goes into ONE table with ONE schema. Queries and dashboards read from here.

Schema:
  source:  telegram | ci | lima_code | vps_smoke | device_gateway | esp32
  loop:    chat_ide | limacode_worker | device_gateway | backend_eval | ops_learning
  outcome: success | failure | partial
  learned: 0=unlearned | 1=learned | 2=rejected | 3=applied
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "outcome_ledger.db")
_DB_PATH = os.environ.get("LIMA_OUTCOME_DB", _DEFAULT_DB_PATH)
_ENABLED = os.environ.get("LIMA_OUTCOME_LEDGER", "1").strip().lower() in {"1", "true", "yes"}

ALLOWED_LOOPS = {
    "chat_ide", "limacode_worker", "device_gateway",
    "backend_eval", "ops_learning",
}


def get_db_path() -> str:
    """Return the current outcome DB path, honoring test/runtime env changes."""
    return os.environ.get("LIMA_OUTCOME_DB", _DB_PATH)


def _clean_text(text: str, max_len: int = 500) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", cleaned)
    for pattern in ("sk-", "gho_", "ghp_", "github_pat_"):
        cleaned = re.sub(rf"(^|\s)({re.escape(pattern)}\S+)", r"\1[REDACTED]", cleaned)
    return cleaned[:max_len]


def _clean_value(value: Any, *, max_items: int = 50) -> Any:
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, dict):
        return {
            _clean_text(str(k), 80): _clean_value(v, max_items=max_items)
            for k, v in list(value.items())[:max_items]
        }
    if isinstance(value, (list, tuple)):
        return [_clean_value(v, max_items=max_items) for v in list(value)[:max_items]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean_text(str(value))


def _clean_list(values: list[str] | None, *, max_items: int = 10) -> list[Any]:
    return [_clean_value(v) for v in list(values or [])[:max_items]]


def _json_loads_safe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def _get_conn() -> sqlite3.Connection:
    db_path = get_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            loop TEXT DEFAULT '',
            outcome TEXT NOT NULL DEFAULT 'success',
            backend TEXT DEFAULT '',
            scenario TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            device_id TEXT DEFAULT '',
            request_id TEXT DEFAULT '',
            entrypoint TEXT DEFAULT '',
            fallback_used INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            summary TEXT DEFAULT '',
            details TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            evidence TEXT DEFAULT '[]',
            artifact_paths TEXT DEFAULT '[]',
            rollback TEXT DEFAULT '',
            recorded_at REAL NOT NULL,
            learned INTEGER DEFAULT 0
        )
    """)
    for col, col_type in [
        ("loop", "TEXT DEFAULT ''"),
        ("device_id", "TEXT DEFAULT ''"),
        ("request_id", "TEXT DEFAULT ''"),
        ("entrypoint", "TEXT DEFAULT ''"),
        ("fallback_used", "INTEGER DEFAULT 0"),
        ("latency_ms", "INTEGER DEFAULT 0"),
        ("evidence", "TEXT DEFAULT '[]'"),
        ("artifact_paths", "TEXT DEFAULT '[]'"),
        ("rollback", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE outcomes ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_source ON outcomes(source, recorded_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_task ON outcomes(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_loop ON outcomes(loop, outcome)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_unlearned ON outcomes(learned, recorded_at)")
    conn.commit()
    return conn


def _make_id(source: str) -> str:
    return f"{source}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}"


def record(
    source: str,
    event_type: str,
    outcome: str = "success",
    *,
    loop: str = "",
    backend: str = "",
    scenario: str = "",
    task_id: str = "",
    device_id: str = "",
    request_id: str = "",
    entrypoint: str = "",
    fallback_used: bool = False,
    latency_ms: int = 0,
    summary: str = "",
    details: dict | None = None,
    tags: list[str] | None = None,
    evidence: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    rollback: str = "",
) -> str | None:
    """Record an outcome event. Returns event_id or None."""
    if not _ENABLED:
        return None

    event_id = _make_id(source)
    clean_source = _clean_text(source, 80)
    clean_event_type = _clean_text(event_type, 80)
    clean_outcome = _clean_text(outcome, 80)
    clean_loop = _clean_text(loop, 80)
    clean_backend = _clean_text(backend, 80)
    clean_scenario = _clean_text(scenario, 80)
    clean_task_id = _clean_text(task_id, 120)
    clean_device_id = _clean_text(device_id, 120)
    clean_request_id = _clean_text(request_id, 120)
    clean_entrypoint = _clean_text(entrypoint, 120)
    clean_evidence = _clean_list(evidence, max_items=10)
    clean_artifacts = _clean_list(artifact_paths, max_items=10)
    conn = _get_conn()
    conn.execute(
        "INSERT INTO outcomes (event_id, source, event_type, loop, outcome, backend, scenario, "
        "task_id, device_id, request_id, entrypoint, fallback_used, latency_ms, "
        "summary, details, tags, evidence, artifact_paths, rollback, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id, clean_source, clean_event_type, clean_loop, clean_outcome,
            clean_backend, clean_scenario,
            clean_task_id, clean_device_id, clean_request_id, clean_entrypoint,
            1 if fallback_used else 0, max(0, int(latency_ms or 0)),
            _clean_text(summary, 500), json.dumps(_clean_value(details or {}), ensure_ascii=False),
            json.dumps(_clean_list(tags, max_items=20), ensure_ascii=False),
            json.dumps(clean_evidence, ensure_ascii=False),
            json.dumps(clean_artifacts, ensure_ascii=False),
            _clean_text(rollback, 500),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()
    return event_id


# ── Capability Evidence wrapper (backwards-compatible) ──


def record_evidence(
    *,
    loop: str,
    request_id: str = "",
    task_id: str = "",
    device_id: str = "",
    entrypoint: str = "",
    selected_backend: str = "",
    fallback_used: bool = False,
    latency_ms: int = 0,
    status: str = "ok",
    evidence: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    rollback: str = "",
) -> dict[str, Any]:
    """Record capability evidence (same store, different interface)."""
    if loop not in ALLOWED_LOOPS:
        raise ValueError(f"unsupported capability loop: {loop}")
    clean_evidence = _clean_list(evidence, max_items=10)
    clean_artifacts = _clean_list(artifact_paths, max_items=10)
    record(
        source="evidence",
        event_type=loop,
        outcome=status,
        loop=loop,
        request_id=request_id,
        task_id=task_id,
        device_id=device_id,
        entrypoint=entrypoint,
        backend=selected_backend,
        fallback_used=fallback_used,
        latency_ms=latency_ms,
        evidence=clean_evidence,
        artifact_paths=clean_artifacts,
        rollback=rollback,
    )
    return {
        "schema_version": "lima.capability_evidence.v0",
        "loop": loop, "status": status,
        "request_id": request_id, "task_id": task_id, "device_id": device_id,
        "entrypoint": entrypoint, "selected_backend": selected_backend,
        "fallback_used": fallback_used, "latency_ms": latency_ms,
        "evidence": clean_evidence, "artifact_paths": clean_artifacts,
        "rollback": rollback, "created_at": time.time(),
    }


def record_evidence_safe(**kwargs: Any) -> dict[str, Any] | None:
    """Best-effort evidence write; never raises to callers."""
    try:
        return record_evidence(**kwargs)
    except Exception:
        _log.warning("record_evidence failed loop=%s", kwargs.get("loop", "?"), exc_info=True)
        return None


def recent_evidence(*, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent evidence rows from the unified store."""
    return query_events(limit=limit)


# ── Query/Mark functions — delegated to outcome_queries.py ──

from session_memory.outcome_queries import (  # noqa: F401
    query_events,
    query,
    stats,
    mark_learned,
    mark_rejected,
    mark_applied,
)
