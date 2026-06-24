"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from device_logic.http import (
    err,
    expires_at,
    json_params,
    loads_json,
    new_id,
    now,
    ok,
    query_int,
    read_body,
    str_field,
)

__all__ = [
    "err",
    "expires_at",
    "json_params",
    "loads_json",
    "new_id",
    "now",
    "ok",
    "query_int",
    "read_body",
    "str_field",
]
