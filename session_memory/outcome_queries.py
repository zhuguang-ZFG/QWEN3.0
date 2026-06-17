"""Outcome Ledger — query, stats, and state machine operations.

Extracted from outcome_ledger.py for file-size compliance.
All functions depend on _get_conn() from the parent module.
"""

from __future__ import annotations

import json
import logging

from session_memory.outcome_ledger import _get_conn, _json_loads_safe

_log = logging.getLogger(__name__)


def _row_to_dict(r: tuple) -> dict:
    d = {
        "event_id": r[0],
        "source": r[1],
        "event_type": r[2],
        "loop": r[3],
        "outcome": r[4],
        "backend": r[5],
        "scenario": r[6],
        "task_id": r[7],
        "device_id": r[8],
        "request_id": r[9],
        "entrypoint": r[10],
        "fallback_used": bool(r[11]),
        "latency_ms": r[12],
        "summary": r[13],
        "tags": _json_loads_safe(r[14]),
        "evidence": _json_loads_safe(r[15]),
        "artifact_paths": _json_loads_safe(r[16]),
        "rollback": r[17],
        "recorded_at": r[18],
        "learned": r[19],
    }
    d["status"] = d["outcome"]
    d["selected_backend"] = d["backend"]
    d["schema_version"] = "lima.capability_evidence.v0"
    return d


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
            "event_id": r[0],
            "source": r[1],
            "event_type": r[2],
            "outcome": r[3],
            "backend": r[4],
            "scenario": r[5],
            "task_id": r[6],
            "summary": r[7],
            "tags": json.loads(r[8]),
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
