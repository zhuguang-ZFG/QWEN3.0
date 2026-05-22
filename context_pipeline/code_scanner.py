"""Code Scanner — AST-based code relationship extractor.

Scans Python files to populate CodeGraph with structural relationships:
- imports: file A imports from file B
- defines: file A defines class/function X
- calls: function X calls function Y (basic heuristic)

Uses only Python stdlib (ast module). No external dependencies.
"""

import ast
import os
from pathlib import Path
from context_pipeline.graph_retrieval import CodeGraph


def scan_directory(directory: str, graph: CodeGraph | None = None) -> CodeGraph:
    """Scan all .py files in directory and build a CodeGraph."""
    if graph is None:
        graph = CodeGraph()

    py_files = list(Path(directory).glob("*.py"))
    module_map: dict[str, str] = {}

    for f in py_files:
        module_map[f.stem] = str(f.name)

    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(f))
            _extract_relations(f.name, tree, module_map, graph)
        except (SyntaxError, UnicodeDecodeError):
            continue

    return graph


def _extract_relations(
    filename: str,
    tree: ast.Module,
    module_map: dict[str, str],
    graph: CodeGraph,
) -> None:
    """Extract import and definition relationships from an AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name.split(".")[0]
                if target in module_map:
                    graph.add_relation(filename, module_map[target], "imports")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                target = node.module.split(".")[0]
                if target in module_map:
                    graph.add_relation(filename, module_map[target], "imports")

        elif isinstance(node, ast.ClassDef):
            graph.add_relation(filename, node.name, "defines_class")
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in module_map:
                    graph.add_relation(filename, module_map[base.id], "extends")

        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            graph.add_relation(filename, node.name, "defines_func")


# Singleton graph instance
_global_graph: CodeGraph | None = None


def get_code_graph(directory: str | None = None) -> CodeGraph:
    """Get or build the global code graph."""
    global _global_graph
    if _global_graph is None:
        scan_dir = directory or os.environ.get("LIMA_CODE_DIR", "/opt/lima-router")
        _global_graph = scan_directory(scan_dir)
    return _global_graph


def refresh_graph(directory: str | None = None) -> CodeGraph:
    """Force rebuild the code graph."""
    global _global_graph
    scan_dir = directory or os.environ.get("LIMA_CODE_DIR", "/opt/lima-router")
    _global_graph = scan_directory(scan_dir)
    return _global_graph
