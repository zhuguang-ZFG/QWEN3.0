"""Recording functions for outcome events and capability evidence."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any

from session_memory.outcome_ledger.config import _ENABLED, ALLOWED_LOOPS
from session_memory.outcome_ledger.db import _get_conn, _make_id
from session_memory.outcome_ledger.sanitize import _clean_list, _clean_text, _clean_value
from session_memory.outcome_queries import query_events

_log = logging.getLogger(__name__)


def _prepare_record_values(
    event_id: str,
    source: str,
    event_type: str,
    outcome: str,
    loop: str,
    backend: str,
    scenario: str,
    task_id: str,
    device_id: str,
    request_id: str,
    entrypoint: str,
    fallback_used: bool,
    latency_ms: int,
    summary: str,
    details: dict | None,
    tags: list[str] | None,
    evidence: list[str] | None,
    artifact_paths: list[str] | None,
    rollback: str,
) -> dict[str, Any]:
    """Build the sanitized value dict for an INSERT, preserving all cleaning rules."""
    clean_evidence = _clean_list(evidence, max_items=10)
    clean_artifacts = _clean_list(artifact_paths, max_items=10)
    return {
        "event_id": event_id,
        "source": _clean_text(source, 80),
        "event_type": _clean_text(event_type, 80),
        "loop": _clean_text(loop, 80),
        "outcome": _clean_text(outcome, 80),
        "backend": _clean_text(backend, 80),
        "scenario": _clean_text(scenario, 80),
        "task_id": _clean_text(task_id, 120),
        "device_id": _clean_text(device_id, 120),
        "request_id": _clean_text(request_id, 120),
        "entrypoint": _clean_text(entrypoint, 120),
        "fallback_used": 1 if fallback_used else 0,
        "latency_ms": max(0, int(latency_ms or 0)),
        "summary": _clean_text(summary, 500),
        "details": json.dumps(_clean_value(details or {}), ensure_ascii=False),
        "tags": json.dumps(_clean_list(tags, max_items=20), ensure_ascii=False),
        "evidence": json.dumps(clean_evidence, ensure_ascii=False),
        "artifact_paths": json.dumps(clean_artifacts, ensure_ascii=False),
        "rollback": _clean_text(rollback, 500),
        "recorded_at": time.time(),
    }


def _insert_outcome_record(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Execute INSERT, commit, and close the connection."""
    conn.execute(
        "INSERT INTO outcomes (event_id, source, event_type, loop, outcome, backend, scenario, "
        "task_id, device_id, request_id, entrypoint, fallback_used, latency_ms, "
        "summary, details, tags, evidence, artifact_paths, rollback, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(
            values[col]
            for col in [
                "event_id",
                "source",
                "event_type",
                "loop",
                "outcome",
                "backend",
                "scenario",
                "task_id",
                "device_id",
                "request_id",
                "entrypoint",
                "fallback_used",
                "latency_ms",
                "summary",
                "details",
                "tags",
                "evidence",
                "artifact_paths",
                "rollback",
                "recorded_at",
            ]
        ),
    )
    conn.commit()
    conn.close()


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
    values = _prepare_record_values(
        event_id,
        source,
        event_type,
        outcome,
        loop,
        backend,
        scenario,
        task_id,
        device_id,
        request_id,
        entrypoint,
        fallback_used,
        latency_ms,
        summary,
        details,
        tags,
        evidence,
        artifact_paths,
        rollback,
    )
    conn = _get_conn()
    _insert_outcome_record(conn, values)
    return event_id


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
        "loop": loop,
        "status": status,
        "request_id": request_id,
        "task_id": task_id,
        "device_id": device_id,
        "entrypoint": entrypoint,
        "selected_backend": selected_backend,
        "fallback_used": fallback_used,
        "latency_ms": latency_ms,
        "evidence": clean_evidence,
        "artifact_paths": clean_artifacts,
        "rollback": rollback,
        "created_at": time.time(),
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
