"""Memory schemas for device personalization."""

from enum import Enum
from pydantic import BaseModel


class MemoryType(str, Enum):
    """Memory entry types."""

    PREFERENCE = "preference"  # User preference (e.g., favorite color)
    DEVICE_FAILURE = "device_failure"  # Device-specific failure pattern
    TASK_EPISODE = "task_episode"  # Structured task execution record
    PROCEDURE_CONFIDENCE = "procedure_confidence"  # Learned procedure confidence


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    device_id: str
    type: MemoryType
    key: str  # e.g., "favorite_color", "feed_rate_failure"
    value: str  # JSON-encoded structured data
    ttl_days: int  # Time-to-live in days
    created_at: int  # Unix timestamp
    source: str  # e.g., "user_explicit", "inferred_from_task"
    confidence: float = 1.0  # 0.0-1.0
    disabled: bool = False  # Parent can disable learned assumption
