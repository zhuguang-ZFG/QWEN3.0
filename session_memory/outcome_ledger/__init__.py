"""Unified Event Store — single table for all LiMa outcomes and evidence.

Replaces: outcome_ledger + capability_evidence (merged 2026-05-27).
Every event — chat turn, CI run, device task, worker result, eval report —
goes into ONE table with ONE schema. Queries and dashboards read from here.

Schema:
  source:  ci | agent_worker | vps_smoke | device_gateway | esp32
  loop:    chat_ide | agent_worker | device_gateway | backend_eval | ops_learning
  outcome: success | failure | partial
  learned: 0=unlearned | 1=learned | 2=rejected | 3=applied
"""

from __future__ import annotations

from session_memory.outcome_ledger.config import (
    _DEFAULT_DB_PATH,
    _DB_PATH,
    _ENABLED,
    ALLOWED_LOOPS,
    get_db_path,
)
from session_memory.outcome_ledger.db import _get_conn
from session_memory.outcome_ledger.record import (
    record,
    record_evidence,
    record_evidence_safe,
    recent_evidence,
)
from session_memory.outcome_ledger.sanitize import _json_loads_safe
from session_memory.outcome_queries import (
    mark_applied,
    mark_learned,
    mark_rejected,
    query,
    query_events,
    stats,
)

__all__ = [
    "ALLOWED_LOOPS",
    "get_db_path",
    "mark_applied",
    "mark_learned",
    "mark_rejected",
    "query",
    "query_events",
    "record",
    "record_evidence",
    "record_evidence_safe",
    "recent_evidence",
    "stats",
    "_DB_PATH",
    "_DEFAULT_DB_PATH",
    "_ENABLED",
    "_get_conn",
    "_json_loads_safe",
]
