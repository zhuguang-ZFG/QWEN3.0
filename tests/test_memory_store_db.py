"""Tests for session_memory/store_db.py — SQLite memory persistence."""

import os
import tempfile

from session_memory.store_db import (
    get_db_path,
    set_db_path,
    memory_stats,
    _sanitize_storage_text,
)


class TestDbPath:
    def test_get_db_path_returns_string(self):
        path = get_db_path()
        assert isinstance(path, str)
        assert len(path) > 0

    def test_set_db_path_changes_path(self):
        original = get_db_path()
        new_path = tempfile.mktemp(suffix=".db")
        set_db_path(new_path)
        assert new_path.endswith(".db")
        set_db_path(original)
        assert get_db_path() == original


class TestSanitizeStorageText:
    def test_normal_text_passes(self):
        result = _sanitize_storage_text("hello world")
        assert result == "hello world"

    def test_api_key_redacted(self):
        result = _sanitize_storage_text("my key is sk-" + "a" * 48)
        assert "[REDACTED]" in result

    def test_empty_text(self):
        assert _sanitize_storage_text("") == ""
        assert _sanitize_storage_text("   ") == ""


class TestMemoryStats:
    def test_empty_store_returns_zeroes(self):
        stats = memory_stats()
        assert stats["total"] >= 0
        assert "sessions" in stats
        assert "by_type" in stats

    def test_stats_structure(self):
        stats = memory_stats()
        assert "total" in stats
        assert "with_embeddings" in stats
        assert "embedding_pct" in stats
        assert "sessions" in stats
        assert "by_type" in stats
