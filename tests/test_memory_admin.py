"""Tests for session_memory/store_admin.py — memory admin operations."""

from __future__ import annotations

from unittest.mock import patch

from config.settings import SESSION_MEMORY
from session_memory.store import get_recent_memories, save_memory
from session_memory.store_admin import (
    can_delete_memories,
    can_export_memories,
    count_memories,
    delete_memories_by_type,
    delete_memory,
    export_session_json,
)


class TestDeleteMemory:
    def test_delete_existing_memory(self):
        eid = save_memory("test_del", "user", "hello world")
        assert eid > 0
        assert delete_memory(eid) is True

    def test_delete_nonexistent_memory(self):
        assert delete_memory(999999) is False


class TestDeleteMemoriesByType:
    def test_delete_by_type(self):
        save_memory("s1", "user", "test", memory_type="code_fact")
        save_memory("s1", "user", "test2", memory_type="exchange")
        with patch.object(SESSION_MEMORY, "admin", True):
            deleted = delete_memories_by_type("code_fact")
            assert deleted >= 1

    def test_delete_without_admin_returns_zero(self):
        with patch.object(SESSION_MEMORY, "admin", False):
            assert delete_memories_by_type("exchange") == 0


class TestCanDelete:
    def test_default_false(self):
        with patch.object(SESSION_MEMORY, "admin", False):
            assert can_delete_memories() is False

    def test_enabled(self):
        with patch.object(SESSION_MEMORY, "admin", True):
            assert can_delete_memories() is True


class TestCanExport:
    def test_default_false(self):
        with patch.object(SESSION_MEMORY, "admin", False):
            assert can_export_memories() is False

    def test_enabled(self):
        with patch.object(SESSION_MEMORY, "admin", True):
            assert can_export_memories() is True


class TestExportSessionJson:
    def test_export_returns_list_with_redacted(self):
        with patch.object(SESSION_MEMORY, "admin", False):
            result = export_session_json("test_sid")
            assert isinstance(result, list)
            assert result[0].get("redacted") is True
