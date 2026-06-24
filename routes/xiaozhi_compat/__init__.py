"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from .shared import (
    authorize,
    connect,
    device_access,
    device_payload,
    err,
    member_payload,
    new_id,
    now,
    ok,
    read_body,
    require_device_access,
    str_field,
    task_payload,
)

__all__ = [
    "authorize",
    "connect",
    "device_access",
    "device_payload",
    "err",
    "member_payload",
    "new_id",
    "now",
    "ok",
    "read_body",
    "require_device_access",
    "str_field",
    "task_payload",
]
