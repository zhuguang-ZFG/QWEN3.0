"""Capability Evidence — thin re-export from the unified Outcome Ledger.

Merged 2026-05-27: all evidence now goes through session_memory.outcome_ledger.
This module exists for backward compatibility only.
"""

from __future__ import annotations

from session_memory.outcome_ledger import (
    ALLOWED_LOOPS,
    record_evidence,
    record_evidence_safe,
    recent_evidence,
)

__all__ = ["record_evidence", "record_evidence_safe", "recent_evidence", "ALLOWED_LOOPS"]
