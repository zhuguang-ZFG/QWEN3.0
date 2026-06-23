"""Tests for code_context graph_index."""


def test_in_memory_graph_index_add_and_get_related():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("a.py", "b.py", "imports")
    g.add_relation("a.py", "Calculator", "defines_class")

    related = g.get_related("a.py", max_depth=1)
    assert len(related) >= 2
    targets = {r.target for r in related}
    assert "b.py" in targets
    assert "Calculator" in targets


def test_in_memory_graph_index_bfs_depth_limit():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("a.py", "b.py", "imports")
    g.add_relation("b.py", "c.py", "imports")
    g.add_relation("c.py", "d.py", "imports")

    # depth=2: processes a.py, b.py, c.py - all their outgoing edges
    depth2 = {r.target for r in g.get_related("a.py", max_depth=2)}
    assert "d.py" in depth2

    # depth=0: only processes a.py - only a.py's immediate neighbors
    depth0 = {r.target for r in g.get_related("a.py", max_depth=0)}
    assert "b.py" in depth0
    assert "c.py" not in depth0
    assert "d.py" not in depth0


def test_in_memory_graph_index_search():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("mod_a.py", "mod_b.py", "imports")
    g.add_relation("mod_a.py", "Helper", "defines_class")
    g.add_relation("mod_b.py", "Util", "defines_class")

    results = g.search(["mod_a.py"], max_depth=2, max_results=10)
    assert len(results) >= 2


def test_in_memory_graph_index_edge_count():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    assert g.edge_count == 0
    g.add_relation("a.py", "b.py", "imports")
    assert g.edge_count == 1


def test_graph_index_is_abstract():
    from code_context.graph_index import GraphIndex
    import pytest

    with pytest.raises(TypeError):
        GraphIndex()


def test_build_graph_index_factory():
    from code_context.graph_index import build_graph_index, GraphIndex

    g = build_graph_index()
    assert isinstance(g, GraphIndex)
