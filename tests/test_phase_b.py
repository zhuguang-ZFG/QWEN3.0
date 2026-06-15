"""Tests for B1 (auto-indexer)."""

from __future__ import annotations

from context_pipeline.auto_indexer import AutoIndexer


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
