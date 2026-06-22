"""Tests for code_context factory functions with config-driven defaults."""

import os

from code_context.graph_index import build_graph_index
from code_context.index_store import build_code_index

# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class TestFactories:
    def test_build_graph_index_default(self):
        """With LIMA_DATA_DIR set (via conftest), SqliteGraphIndex is returned."""
        g = build_graph_index()
        from code_context.sqlite_graph_store import SqliteGraphIndex

        assert isinstance(g, SqliteGraphIndex)

    def test_build_graph_index_persistent(self, tmp_path):
        """Custom LIMA_DATA_DIR passed through config."""
        fresh = tmp_path / "fresh_graph"
        fresh.mkdir()
        os.environ["LIMA_DATA_DIR"] = str(fresh)
        try:
            g = build_graph_index()
            g.add_relation("a.py", "b.py", "imports")
            assert g.edge_count >= 1
        finally:
            os.environ.pop("LIMA_DATA_DIR", None)

    def test_build_code_index_default(self):
        """With LIMA_DATA_DIR set (via conftest), ChromaCodeIndex or fallback."""
        idx = build_code_index()
        assert idx is not None
        assert hasattr(idx, "search")

    def test_build_code_index_persistent(self, tmp_path):
        """Custom LIMA_DATA_DIR for code index."""
        fresh = tmp_path / "fresh_code"
        fresh.mkdir()
        os.environ["LIMA_DATA_DIR"] = str(fresh)
        try:
            idx = build_code_index()
            assert idx is not None
        finally:
            os.environ.pop("LIMA_DATA_DIR", None)
