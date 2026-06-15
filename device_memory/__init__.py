"""Device Memory: Safe personalization without storing raw child media.

Stores structured task episodes, preferences, and learned patterns.
Provides TTL filtering, cross-family isolation, and parent controls.
"""
from device_memory.store import MemoryStore, configure_memory_store_from_env, get_memory_store
from device_memory.schemas import MemoryEntry, MemoryType
from device_memory.extractor import extract_episode_from_terminal, extract_device_failure_from_event
from device_memory.consolidation import consolidate_task_episodes
from device_memory.recall import recall_planner_hints, get_device_failure_warnings
from device_memory.quality_gates import is_safe_for_recall, should_learn_entry

__all__ = [
    "MemoryStore",
    "get_memory_store",
    "configure_memory_store_from_env",
    "MemoryEntry",
    "MemoryType",
    "extract_episode_from_terminal",
    "extract_device_failure_from_event",
    "consolidate_task_episodes",
    "recall_planner_hints",
    "get_device_failure_warnings",
    "is_safe_for_recall",
    "should_learn_entry",
]
