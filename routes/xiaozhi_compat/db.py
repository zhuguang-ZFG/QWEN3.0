"""Backward-compatible re-export — canonical implementation in device_logic.db."""

from device_logic.db import (
    _schema_lock,
    _schema_ready_paths,
    connect,
    db_path,
    ensure_schema,
)

__all__ = [
    "_schema_lock",
    "_schema_ready_paths",
    "connect",
    "db_path",
    "ensure_schema",
]
