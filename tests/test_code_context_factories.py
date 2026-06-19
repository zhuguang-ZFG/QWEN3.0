"""Tests for code context factory functions."""

import os

from code_context.graph_index import InMemoryGraphIndex, build_graph_index
from code_context.index_store import InMemoryCodeIndex, build_code_index


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class TestFactories:
    def test_build_graph_index_default(self):
        os.environ.pop("LIMA_DATA_DIR", None)
        g = build_graph_index()
        assert isinstance(g, InMemoryGraphIndex)

    def test_build_graph_index_persistent(self, tmp_path):
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
        os.environ.pop("LIMA_DATA_DIR", None)
        idx = build_code_index()
        assert isinstance(idx, InMemoryCodeIndex)
