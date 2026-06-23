"""Tests for session_memory/embeddings.py — embedding generation."""

from unittest.mock import patch

from session_memory.embeddings import _generate_embedding, save_memory_with_embedding, _EMBED_ENABLED


class TestGenerateEmbedding:
    def test_disabled_returns_empty(self):
        with patch("session_memory.embeddings._EMBED_ENABLED", False):
            assert _generate_embedding("test") == []

    def test_empty_text_returns_empty(self):
        assert _generate_embedding("") == []

    def test_no_api_key_returns_empty(self):
        with patch("session_memory.embeddings._EMBED_ENABLED", True):
            with patch.dict("os.environ", {}, clear=True):
                assert _generate_embedding("test") == []


class TestSaveMemoryWithEmbedding:
    def test_disabled_still_saves(self):
        with patch("session_memory.embeddings._EMBED_ENABLED", False):
            eid = save_memory_with_embedding("sid", "user", "test")
            assert eid > 0

    def test_saves_without_embedding_when_disabled(self):
        with patch("session_memory.embeddings._EMBED_ENABLED", False):
            eid = save_memory_with_embedding("sid2", "user", "content", memory_type="code_fact")
            assert eid > 0

    def test_embed_enabled_default(self):
        assert _EMBED_ENABLED is True
