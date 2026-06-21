"""Shared constants for device app task/member validation."""

ALLOWED_TASKS = frozenset({"run_path", "draw_image", "home", "calibrate"})
ALLOWED_SOURCES = frozenset({"api", "voice", "scheduled"})
ALLOWED_MEMBER_ROLES = frozenset({"child", "parent", "guest"})
ALLOWED_TASK_STATUSES = frozenset(
    {
        "pending",
        "approved",
        "running",
        "completed",
        "failed",
        "cancelled",
        "rejected",
    }
)
