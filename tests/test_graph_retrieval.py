"""Tests for context_pipeline/graph_retrieval.py — code graph operations."""

from context_pipeline.graph_retrieval import CodeGraph, RetrievalResult, CodeRelation


class TestCodeGraph:
    def test_add_relation(self):
        g = CodeGraph()
        g.add_relation("a.py", "b.py", "imports")
        related = g.get_related("a.py")
        assert len(related) >= 1
        assert any(r.target == "b.py" for r in related)

    def test_empty_graph(self):
        g = CodeGraph()
        assert g.get_related("nonexistent") == []

    def test_bidirectional_edge(self):
        g = CodeGraph()
        g.add_relation("a.py", "b.py", "imports")
        related_a = g.get_related("a.py")
        related_b = g.get_related("b.py")
        assert len(related_a) >= 1
        assert len(related_b) >= 1

    def test_multiple_relations(self):
        g = CodeGraph()
        g.add_relation("a.py", "b.py", "imports")
        g.add_relation("a.py", "c.py", "calls")
        related = g.get_related("a.py", max_depth=1)
        assert len(related) >= 2

    def test_edge_count(self):
        g = CodeGraph()
        assert g.edge_count == 0
        g.add_relation("a.py", "b.py", "imports")
        assert g.edge_count >= 1

    def test_max_depth_limits_results(self):
        g = CodeGraph()
        g.add_relation("a.py", "b.py", "imports")
        g.add_relation("b.py", "c.py", "imports")
        shallow = g.get_related("a.py", max_depth=0)
        deep = g.get_related("a.py", max_depth=2)
        assert len(deep) > len(shallow)


class TestRetrievalResult:
    def test_default_values(self):
        r = RetrievalResult(path="test.py", score=0.5, source="vector")
        assert r.snippet == ""
        assert r.relations == []


class TestCodeRelation:
    def test_default_weight(self):
        r = CodeRelation(source="a", target="b", relation_type="imports")
        assert r.weight == 1.0
