"""Unified Outcome Ledger — normalize events from all LiMa subsystems.

Sources: Telegram, CI, LiMa Code, VPS smoke, ESP32/Device Gateway.
Each event is a timestamped outcome record that feeds into:
  - session_memory (typed memories)
  - routing_weights (backend quality signals)
  - eval candidates (pattern extraction)
  - mastery_loop (skill profiles)

Schema:
  source:   telegram | ci | lima_code | vps_smoke | device_gateway | esp32
  outcome:  success | failure | partial
  scenario: coding | chat | device | ops | eval | deploy
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

_log = logging.getLogger(__name__)

_DB_PATH = os.environ.get("LIMA_OUTCOME_DB", str(Path(__file__).resolve().parent.parent / "data" / "outcome_ledger.db"))
_ENABLED = os.environ.get("LIMA_OUTCOME_LEDGER", "1").strip().lower() in {"1", "true", "yes"}


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
            outcome TEXT NOT NULL DEFAULT 'success',
            backend TEXT DEFAULT '',
            scenario TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            details TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            recorded_at REAL NOT NULL,
            learned INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_source ON outcomes(source, recorded_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_task ON outcomes(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_scenario ON outcomes(scenario, outcome)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_unlearned ON outcomes(learned, recorded_at)")
    conn.commit()
    return conn


def _make_id(source: str) -> str:
    import uuid
    ts = int(time.time() * 1000)
    return f"{source}:{ts}:{uuid.uuid4().hex[:8]}"


def record(
    source: str,
    event_type: str,
    outcome: str = "success",
    *,
    backend: str = "",
    scenario: str = "",
    task_id: str = "",
    summary: str = "",
    details: dict | None = None,
    tags: list[str] | None = None,
) -> str | None:
    """Record an outcome event. Returns event_id or None."""
    if not _ENABLED:
        return None

    event_id = _make_id(source)
    conn = _get_conn()
    conn.execute(
        "INSERT INTO outcomes (event_id, source, event_type, outcome, backend, scenario, task_id, summary, details, tags, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id, source, event_type, outcome, backend, scenario,
            task_id, summary[:500], json.dumps(details or {}, ensure_ascii=False),
            json.dumps(tags or []), time.time(),
        ),
    )
    conn.commit()
    conn.close()
    _log.debug("outcome recorded: %s %s %s", source, event_type, outcome)
    return event_id


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
    conn.close()
    return {
        "total": total,
        "unlearned": unlearned,
        "by_source": {r[0]: {"total": r[1], "success": r[2]} for r in by_source},
        "by_scenario": {r[0]: {"total": r[1], "success": r[2]} for r in by_scenario},
    }
