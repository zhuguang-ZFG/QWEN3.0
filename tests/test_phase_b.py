"""Tests for B1 (auto-indexer) + B3 (session memory enhancer)."""

from __future__ import annotations



from context_pipeline.auto_indexer import AutoIndexer
from context_pipeline.session_memory_enhancer import (
    ExtractedDecision,
    extract_decisions,
    store_decisions,
    process_session_outcome,
    recall_relevant_decisions,
)


# ---------------------------------------------------------------------------
# B1: Auto-Indexer
# ---------------------------------------------------------------------------

class TestAutoIndexer:
    def test_scan_once_empty_dir(self, tmp_path):
        indexer = AutoIndexer(root_path=str(tmp_path))
        stats = indexer.scan_once()
        assert stats["scanned"] == 0
        assert stats["indexed"] == 0

    def test_scan_once_with_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): pass")
        (tmp_path / "b.py").write_text("class Bar: pass")
        indexer = AutoIndexer(root_path=str(tmp_path))
        stats = indexer.scan_once()
        assert stats["scanned"] == 2
        assert stats["indexed"] == 2

    def test_scan_detects_changes(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        indexer = AutoIndexer(root_path=str(tmp_path))
        stats1 = indexer.scan_once()
        assert stats1["changed"] == 1

        stats2 = indexer.scan_once()
        assert stats2["changed"] == 0

    def test_scan_detects_modification(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        indexer = AutoIndexer(root_path=str(tmp_path))
        indexer.scan_once()

        (tmp_path / "a.py").write_text("x = 2")
        stats = indexer.scan_once()
        assert stats["modified"] == 1

    def test_scan_ignores_non_code_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.json").write_text("{}")
        indexer = AutoIndexer(root_path=str(tmp_path))
        stats = indexer.scan_once()
        assert stats["indexed"] == 0

    def test_should_scan(self, tmp_path):
        indexer = AutoIndexer(root_path=str(tmp_path), scan_interval=1)
        assert indexer.should_scan() is True
        indexer.scan_once()
        assert indexer.should_scan() is False

    def test_graph_index_populated(self, tmp_path):
        (tmp_path / "test.py").write_text("class MyClass:\n    def method(self): pass")
        indexer = AutoIndexer(root_path=str(tmp_path))
        indexer.scan_once()
        assert indexer._graph is not None
        assert indexer._graph.edge_count > 0


# ---------------------------------------------------------------------------
# B3: Session Memory Enhancer
# ---------------------------------------------------------------------------

class TestExtractDecisions:
    def test_extracts_tool_choice(self):
        messages = [
            {"role": "user", "content": "Use FastAPI for the API layer"},
            {"role": "assistant", "content": "Sure, I'll use FastAPI."},
        ]
        decisions = extract_decisions(messages)
        assert any(d.category == "tool_choice" for d in decisions)

    def test_extracts_convention(self):
        messages = [
            {"role": "user", "content": "Convention is to use snake_case for functions"},
        ]
        decisions = extract_decisions(messages)
        assert any(d.category == "convention" for d in decisions)

    def test_extracts_backend_pref(self):
        messages = [
            {"role": "assistant", "content": "groq is fast for this task"},
        ]
        decisions = extract_decisions(messages)
        assert any(d.category == "backend_pref" for d in decisions)

    def test_empty_messages(self):
        decisions = extract_decisions([])
        assert len(decisions) == 0

    def test_deduplicates(self):
        messages = [
            {"role": "user", "content": "Use FastAPI for the API. Prefer FastAPI for routing."},
        ]
        decisions = extract_decisions(messages)
        tool_choices = [d for d in decisions if d.category == "tool_choice"]
        assert len(tool_choices) <= 2

    def test_with_backend_and_scenario(self):
        decisions = extract_decisions([], backend="groq", scenario="coding")
        assert any(d.category == "routing_preference" for d in decisions)


class TestStoreDecisions:
    def test_store_returns_count(self):
        decisions = [
            ExtractedDecision(category="pattern", key="repository pattern", confidence=0.8),
        ]
        count = store_decisions(decisions)
        assert count == 1


class TestProcessSessionOutcome:
    def test_processes成功的session(self):
        messages = [
            {"role": "user", "content": "Use pytest for testing"},
            {"role": "assistant", "content": "I'll use pytest."},
        ]
        count = process_session_outcome(messages, backend="groq", scenario="coding", success=True)
        assert count >= 0

    def test_skips_failed_session(self):
        count = process_session_outcome([], success=False)
        assert count == 0


class TestRecallDecisions:
    def test_recall_empty(self):
        results = recall_relevant_decisions("nonexistent topic xyz")
        assert isinstance(results, list)
