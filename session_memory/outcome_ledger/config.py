"""Configuration constants for the outcome ledger package."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "outcome_ledger.db")
_DB_PATH = os.environ.get("LIMA_OUTCOME_DB", _DEFAULT_DB_PATH)
_ENABLED = os.environ.get("LIMA_OUTCOME_LEDGER", "1").strip().lower() in {"1", "true", "yes"}

ALLOWED_LOOPS = {
    "chat_ide",
    "agent_worker",
    "limacode_worker",
    "device_gateway",
    "backend_eval",
    "ops_learning",
}


def get_db_path() -> str:
    """Return the current outcome DB path, honoring test/runtime env changes."""
    return os.environ.get("LIMA_OUTCOME_DB", _DB_PATH)
