"""Tests for session_memory/store_admin.py — memory admin operations."""

import os
from unittest.mock import patch

from session_memory.store import save_memory, get_recent_memories
from session_memory.store_admin import (
    delete_memory,
    delete_memories_by_type,
    count_memories,
    can_delete_memories,
    can_export_memories,
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
        with patch.dict(os.environ, {"LIMA_MEMORY_ADMIN": "1"}):
            deleted = delete_memories_by_type("code_fact")
            assert deleted >= 1

    def test_delete_without_admin_returns_zero(self):
        with patch.dict(os.environ, {}, clear=True):
            assert delete_memories_by_type("exchange") == 0


class TestCanDelete:
    def test_default_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert can_delete_memories() is False

    def test_enabled(self):
        with patch.dict(os.environ, {"LIMA_MEMORY_ADMIN": "1"}):
            assert can_delete_memories() is True


class TestCanExport:
    def test_default_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert can_export_memories() is False

    def test_enabled(self):
        with patch.dict(os.environ, {"LIMA_MEMORY_ADMIN": "1"}):
            assert can_export_memories() is True


class TestExportSessionJson:
    def test_export_returns_list_with_redacted(self):
        with patch.dict(os.environ, {}, clear=True):
            result = export_session_json("test_sid")
            assert isinstance(result, list)
            assert result[0].get("redacted") is True
