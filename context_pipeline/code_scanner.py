# DEPRECATED v3.0 — coding capability retired
"""Code Scanner — AST-based code relationship extractor (DEPRECATED).

Scans Python files to populate CodeGraph with structural relationships:
- imports: file A imports from file B
- defines: file A defines class/function X
- calls: function X calls function Y (basic heuristic)

Uses only Python stdlib (ast module). No external dependencies.

v3.0: coding capability retired. Main functions are disabled and return
safe default values to keep imports working.
"""

from __future__ import annotations

from context_pipeline.graph_retrieval import CodeGraph


def scan_directory(directory: str, graph: CodeGraph | None = None) -> CodeGraph:
    """Scan all .py files in directory and build a CodeGraph. (DEPRECATED)"""
    return graph if graph is not None else CodeGraph()


def scan_files(file_paths: list[str], graph: CodeGraph | None = None) -> CodeGraph:
    """Scan explicit .py files and build a CodeGraph. (DEPRECATED)"""
    return graph if graph is not None else CodeGraph()


def _extract_relations(
    filename: str,
    tree,
    module_map: dict[str, str],
    graph: CodeGraph,
) -> None:
    """Extract import and definition relationships from an AST. (DEPRECATED)"""
    return None


# Singleton graph instance
_global_graph: CodeGraph | None = None


def reset_code_graph() -> None:
    """Clear cached graph (for tests)."""
    global _global_graph
    _global_graph = None


def get_code_graph(directory: str | None = None) -> CodeGraph:
    """Get or build the global code graph. (DEPRECATED)"""
    global _global_graph
    if _global_graph is None:
        _global_graph = CodeGraph()
    return _global_graph


def refresh_graph(directory: str | None = None) -> CodeGraph:
    """Force rebuild the code graph. (DEPRECATED)"""
    global _global_graph
    _global_graph = CodeGraph()
    return _global_graph
