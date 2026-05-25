"""Session memory store facade (re-exports submodules)."""
from session_memory.store_admin import (
    can_delete_memories,
    can_export_memories,
    delete_memories_by_type,
    delete_memories_older_than,
    delete_memory,
    export_by_type_json,
    export_session_json,
)
from session_memory.store_crud import (
    clear_session,
    count_memories,
    get_recent_memories,
    save_memory,
    search_memories_keyword,
    search_memories_semantic,
)
from session_memory.store_db import MemoryEntry, MEMORY_TYPES, _DB_PATH, _get_conn
from session_memory.store_promote import (
    auto_promote_candidates,
    promote_memory,
    query_by_type,
    save_typed_memory,
)

__all__ = [
    "MemoryEntry",
    "MEMORY_TYPES",
    "_DB_PATH",
    "_get_conn",
    "auto_promote_candidates",
    "can_delete_memories",
    "can_export_memories",
    "clear_session",
    "count_memories",
    "delete_memories_by_type",
    "delete_memories_older_than",
    "delete_memory",
    "export_by_type_json",
    "export_session_json",
    "get_recent_memories",
    "promote_memory",
    "query_by_type",
    "save_memory",
    "save_typed_memory",
    "search_memories_keyword",
    "search_memories_semantic",
]
