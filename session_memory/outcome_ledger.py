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

_DB_PATH = os.environ.get("LIMA_OUTCOME_DB", str(Path(__file__).resolve().parent.parent / "data" / "outcome_ledger.db"))
_ENABLED = os.environ.get("LIMA_OUTCOME_LEDGER", "1").strip().lower() in {"1", "true", "yes"}

ALLOWED_LOOPS = {
    "chat_ide", "limacode_worker", "device_gateway",
    "backend_eval", "ops_learning",
}


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
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
    conn = _get_conn()
    conn.execute(
        "INSERT INTO outcomes (event_id, source, event_type, loop, outcome, backend, scenario, "
        "task_id, device_id, request_id, entrypoint, fallback_used, latency_ms, "
        "summary, details, tags, evidence, artifact_paths, rollback, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id, source, event_type, loop, outcome, backend, scenario,
            task_id, device_id, request_id, entrypoint,
            1 if fallback_used else 0, max(0, int(latency_ms or 0)),
            summary[:500], json.dumps(details or {}, ensure_ascii=False),
            json.dumps(tags or []), json.dumps(evidence or []),
            json.dumps(artifact_paths or []), rollback[:500],
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
        evidence=evidence,
        artifact_paths=artifact_paths,
        rollback=rollback,
    )
    return {
        "schema_version": "lima.capability_evidence.v0",
        "loop": loop, "status": status,
        "request_id": request_id, "task_id": task_id, "device_id": device_id,
        "entrypoint": entrypoint, "selected_backend": selected_backend,
        "fallback_used": fallback_used, "latency_ms": latency_ms,
        "evidence": evidence or [], "artifact_paths": (artifact_paths or [])[:10],
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


def query_events(
    *,
    source: str = "",
    loop: str = "",
    outcome: str = "",
    limit: int = 20,
) -> list[dict]:
    """Query events with optional filters. Replaces query()."""
    conn = _get_conn()
    wheres: list[str] = []
    params: list = []
    if source:
        wheres.append("source = ?")
        params.append(source)
    if loop:
        wheres.append("loop = ?")
        params.append(loop)
    if outcome:
        wheres.append("outcome = ?")
        params.append(outcome)
    where = " AND ".join(wheres) if wheres else "1=1"
    rows = conn.execute(
        f"SELECT event_id, source, event_type, loop, outcome, backend, scenario, "
        f"task_id, device_id, request_id, entrypoint, fallback_used, latency_ms, "
        f"summary, tags, evidence, artifact_paths, rollback, recorded_at, learned "
        f"FROM outcomes WHERE {where} ORDER BY recorded_at DESC LIMIT ?",
        (*params, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r: tuple) -> dict:
    d = {
        "event_id": r[0], "source": r[1], "event_type": r[2], "loop": r[3],
        "outcome": r[4], "backend": r[5], "scenario": r[6],
        "task_id": r[7], "device_id": r[8], "request_id": r[9],
        "entrypoint": r[10], "fallback_used": bool(r[11]), "latency_ms": r[12],
        "summary": r[13], "tags": json.loads(r[14]) if isinstance(r[14], str) else r[14],
        "evidence": json.loads(r[15]) if isinstance(r[15], str) else r[15],
        "artifact_paths": json.loads(r[16]) if isinstance(r[16], str) else r[16],
        "rollback": r[17], "recorded_at": r[18], "learned": r[19],
    }
    d["status"] = d["outcome"]
    d["selected_backend"] = d["backend"]
    d["schema_version"] = "lima.capability_evidence.v0"
    return d


def query(
    *,
    source: str = "",
    scenario: str = "",
    outcome: str = "",
    limit: int = 20,
) -> list[dict]:
    """Query outcome events with optional filters."""
    conn = _get_conn()
    wheres: list[str] = []
    params: list = []
    if source:
        wheres.append("source = ?")
        params.append(source)
    if scenario:
        wheres.append("scenario = ?")
        params.append(scenario)
    if outcome:
        wheres.append("outcome = ?")
        params.append(outcome)
    where = " AND ".join(wheres) if wheres else "1=1"
    rows = conn.execute(
        f"SELECT event_id, source, event_type, outcome, backend, scenario, task_id, summary, tags, recorded_at "
        f"FROM outcomes WHERE {where} ORDER BY recorded_at DESC LIMIT ?",
        (*params, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "event_id": r[0], "source": r[1], "event_type": r[2],
            "outcome": r[3], "backend": r[4], "scenario": r[5],
            "task_id": r[6], "summary": r[7], "tags": json.loads(r[8]),
            "recorded_at": r[9],
        }
        for r in rows
    ]


def stats() -> dict:
    """Return aggregate statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] or 0
    by_source = conn.execute(
        "SELECT source, COUNT(*), SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) FROM outcomes GROUP BY source"
    ).fetchall()
    by_scenario = conn.execute(
        "SELECT scenario, COUNT(*), SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) FROM outcomes GROUP BY scenario"
    ).fetchall()
    unlearned = conn.execute("SELECT COUNT(*) FROM outcomes WHERE learned=0").fetchone()[0] or 0
    rejected = conn.execute("SELECT COUNT(*) FROM outcomes WHERE learned=2").fetchone()[0] or 0
    applied = conn.execute("SELECT COUNT(*) FROM outcomes WHERE learned=3").fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "unlearned": unlearned,
        "rejected": rejected,
        "applied": applied,
        "by_source": {r[0]: {"total": r[1], "success": r[2]} for r in by_source},
        "by_scenario": {r[0]: {"total": r[1], "success": r[2]} for r in by_scenario},
    }


# ── State machine actions (Hermes pattern: evidence-gated transitions) ──
# learned: 0=unlearned, 1=learned, 2=rejected, 3=applied


def mark_learned(event_id: str, *, notes: str = "") -> bool:
    """Mark an outcome as learned (learned=1)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE outcomes SET learned=1, details=json_set(details, '$.learn_notes', ?) WHERE event_id=?",
        (notes[:200], event_id),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        _log.info("outcome marked learned: %s", event_id)
    return affected > 0


def mark_rejected(event_id: str, *, reason: str = "") -> bool:
    """Mark an outcome as rejected (learned=2)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE outcomes SET learned=2, details=json_set(details, '$.reject_reason', ?) WHERE event_id=?",
        (reason[:200], event_id),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        _log.info("outcome rejected: %s (%s)", event_id, reason[:80])
    return affected > 0


def mark_applied(event_id: str, *, notes: str = "") -> bool:
    """Mark an outcome as applied — evidence was used to change routing/prompt."""
    conn = _get_conn()
    conn.execute(
        "UPDATE outcomes SET learned=3, details=json_set(details, '$.apply_notes', ?) WHERE event_id=?",
        (notes[:200], event_id),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        _log.info("outcome applied: %s", event_id)
    return affected > 0
