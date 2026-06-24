"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


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
