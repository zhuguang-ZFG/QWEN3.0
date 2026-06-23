"""Tests for session_memory/embeddings.py — embedding generation."""

from unittest.mock import patch

from session_memory.embeddings import _generate_embedding, save_memory_with_embedding, is_embed_enabled


class TestIsEmbedEnabled:
    def test_enabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_embed_enabled() is True

    def test_disabled(self):
        with patch.dict("os.environ", {"LIMA_MEMORY_EMBED": "0"}):
            assert is_embed_enabled() is False


class TestGenerateEmbedding:
    def test_disabled_returns_empty(self):
        with patch.dict("os.environ", {"LIMA_MEMORY_EMBED": "0"}):
            assert _generate_embedding("test") == []

    def test_empty_text_returns_empty(self):
        assert _generate_embedding("") == []

    def test_no_api_key_returns_empty(self):
        with patch.dict("os.environ", {"LIMA_MEMORY_EMBED": "1"}, clear=True):
            assert _generate_embedding("test") == []


class TestSaveMemoryWithEmbedding:
    def test_disabled_still_saves(self):
        with patch.dict("os.environ", {"LIMA_MEMORY_EMBED": "0"}):
            eid = save_memory_with_embedding("sid", "user", "test")
            assert eid > 0
