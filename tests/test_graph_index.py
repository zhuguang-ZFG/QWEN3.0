"""Tests for in-memory and SQLite graph indexes."""

from code_context.graph_index import (
    InMemoryGraphIndex,
    build_graph_index,
)


# ---------------------------------------------------------------------------
# InMemoryGraphIndex
# ---------------------------------------------------------------------------


class TestInMemoryGraphIndex:
    def test_add_and_search(self):
        g = InMemoryGraphIndex()
        g.add_relation("server.py", "routing_engine.py", "imports")
        g.add_relation("routing_engine.py", "http_caller.py", "calls")
        results = g.search(["server.py"], max_depth=2)
        entities = {r.entity for r in results}
        assert "routing_engine.py" in entities
        assert "http_caller.py" in entities

    def test_edge_count(self):
        g = InMemoryGraphIndex()
        assert g.edge_count == 0
        g.add_relation("a.py", "b.py", "imports")
        assert g.edge_count == 1


# ---------------------------------------------------------------------------
# SQLite Graph Index
# ---------------------------------------------------------------------------


class TestSqliteGraphIndex:
    def test_persistence(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "test_graph.db")
        g1 = SqliteGraphIndex(db)
        g1.add_relation("a.py", "b.py", "imports")
        g1.add_relation("b.py", "c.py", "calls")
        assert g1.edge_count >= 2
        g1.close()

        g2 = SqliteGraphIndex(db)
        assert g2.edge_count >= 2
        results = g2.search(["a.py"], max_depth=2)
        entities = {r.entity for r in results}
        assert "b.py" in entities
        g2.close()

    def test_fts_search(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "fts_test.db")
        g = SqliteGraphIndex(db)
        g.add_relation("server.py", "routing.py", "imports")
        results = g.fts_search("server")
        assert len(results) >= 1
        g.close()

    def test_clear(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "clear_test.db")
        g = SqliteGraphIndex(db)
        g.add_relation("a.py", "b.py", "imports")
        assert g.edge_count >= 1
        g.clear()
        assert g.edge_count == 0
        g.close()
