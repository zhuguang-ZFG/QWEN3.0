"""Anti-learning safety rules for device memory.

Prevents unsafe patterns from being remembered or acted upon.
"""

from __future__ import annotations

from device_memory.schemas import MemoryEntry, MemoryType

# Blocklist: never learn from these task outcomes
_BLOCKED_SOURCES: frozenset[str] = frozenset(
    {
        "manual_override",  # Operator intervention
        "test_task",  # Test/sandbox tasks
        "simulated_failure",  # Injected failures for testing
    }
)

# Blocklist: never personalize based on these capabilities
_BLOCKED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "estop",  # Emergency stop is never a preference
        "unknown",  # Unknown capability type
    }
)

# Minimum confidence threshold before a memory can influence planner
_MIN_RECALL_CONFIDENCE = 0.5


def should_learn_entry(entry: MemoryEntry) -> bool:
    """Check if a memory entry should be stored (anti-learning gate).

    Returns True if the entry passes all safety checks.
    """
    if entry.source in _BLOCKED_SOURCES:
        return False
    if entry.type == MemoryType.PREFERENCE and entry.confidence < 0.3:
        return False
    if entry.type == MemoryType.DEVICE_FAILURE and entry.confidence < 0.5:
        return False
    if entry.type == MemoryType.PROCEDURE_CONFIDENCE and entry.confidence < 0.2:
        return False
    return True


def is_safe_for_recall(entry: MemoryEntry) -> bool:
    """Check if a recalled memory is safe to apply.

    Returns True if the memory can safely influence planner decisions.
    """
    if entry.disabled:
        return False
    if entry.confidence < _MIN_RECALL_CONFIDENCE:
        return False
    return True


def is_hard_safety(path: str) -> bool:
    """Hard safety always overrides learned preferences."""
    return path in (
        "max_path_points",
        "max_feed",
        "workspace_bounds",
        "motion_limits",
        "estop_threshold",
    )
