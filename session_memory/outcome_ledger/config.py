"""Configuration constants for the outcome ledger package."""

from __future__ import annotations

from config.settings import SESSION_MEMORY

_DEFAULT_DB_PATH = SESSION_MEMORY.outcome_db
_DB_PATH = _DEFAULT_DB_PATH
_ENABLED = SESSION_MEMORY.outcome_ledger_enabled

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
    return SESSION_MEMORY.outcome_db
