"""Tests for pipeline_graph."""

from __future__ import annotations

from pipeline_graph import (
    PipelineEdge,
    PipelineGraph,
    PipelineNode,
    build_default_graph,
)


def test_default_graph_has_expected_nodes():
    graph = build_default_graph()
    assert "classify" in graph.nodes
    assert "execute" in graph.nodes
    assert "post_process" in graph.nodes


def test_default_graph_has_expected_edges():
    graph = build_default_graph()
    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert ("identity", "classify") in edge_pairs
    assert ("validate", "post_process") in edge_pairs


def test_to_mermaid_contains_nodes_and_edges():
    graph = PipelineGraph()
    graph.add_node(PipelineNode("a", "Start"))
    graph.add_node(PipelineNode("b", 'End "now"'))
    graph.add_edge(PipelineEdge("a", "b", "go"))
    mmd = graph.to_mermaid()
    assert "flowchart LR" in mmd
    assert 'a["Start"]' in mmd
    assert "b[\"End 'now'\"]" in mmd
    assert 'a -->|"go"| b' in mmd


def test_mermaid_escapes_double_quotes():
    graph = PipelineGraph()
    graph.add_node(PipelineNode("x", 'Say "hi"'))
    mmd = graph.to_mermaid()
    assert "x[\"Say 'hi'\"]" in mmd
