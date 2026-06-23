"""Tests for session_memory/prompt_recall.py — memory recall stats."""

from session_memory.prompt_recall import recall_stats, PromptMemoryRecallResult


class TestRecallStats:
    def test_initial_stats(self, monkeypatch):
        from session_memory import prompt_recall

        monkeypatch.setattr(prompt_recall, "_RECALL_STATS", {"total_checks": 0, "total_hits": 0, "total_chars_added": 0})
        stats = recall_stats()
        assert stats["total_checks"] == 0
        assert stats["total_hits"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["avg_chars_added"] == 0


class TestPromptMemoryRecallResult:
    def test_default_values(self):
        result = PromptMemoryRecallResult(system_prompt="hello")
        assert result.system_prompt == "hello"
        assert result.applied is False
        assert result.session_id == ""
        assert result.prompt_chars_added == 0
        assert result.recalled_memory_ids == []
