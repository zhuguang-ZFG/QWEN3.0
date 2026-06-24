"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from device_logic.constants import (
    ALLOWED_MEMBER_ROLES,
    ALLOWED_SOURCES,
    ALLOWED_TASK_STATUSES,
    ALLOWED_TASKS,
)

__all__ = [
    "ALLOWED_MEMBER_ROLES",
    "ALLOWED_SOURCES",
    "ALLOWED_TASK_STATUSES",
    "ALLOWED_TASKS",
]
