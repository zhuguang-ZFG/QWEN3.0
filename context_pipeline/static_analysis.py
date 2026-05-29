"""Optional static-analysis lane for Python modules.

Narrow, zero-dependency AST lane that extracts typed symbol information
from stable Python modules. Does NOT replace the full retrieval pipeline;
it enriches code graph entries with type/annotation hints when available.

Enabled per-module; gated behind LIMA_STATIC_ANALYSIS env var. Expansion
to the full repo requires evidence that quality improves without hurting
retrieval latency.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field


@dataclass
class TypedSymbol:
    name: str
    kind: str  # "function", "class", "method", "variable"
    line: int
    type_hints: dict[str, str] = field(default_factory=dict)
    docstring: str = ""


def extract_typed_symbols(source: str, filename: str = "<string>") -> list[TypedSymbol]:
    """Extract symbols with type annotations from Python source."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []

    symbols: list[TypedSymbol] = []
    visitor = _SymbolVisitor(symbols)
    visitor.visit(tree)
    return symbols


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, symbols: list[TypedSymbol]) -> None:
        self._symbols = symbols

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        hints: dict[str, str] = {}
        if node.returns:
            hints["returns"] = ast.unparse(node.returns)
        for arg in node.args.args:
            if arg.annotation:
                hints[arg.arg] = ast.unparse(arg.annotation)
        doc = ast.get_docstring(node) or ""
        self._symbols.append(TypedSymbol(
            name=node.name, kind="function", line=node.lineno,
            type_hints=hints, docstring=doc[:200],
        ))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        hints: dict[str, str] = {}
        if node.returns:
            hints["returns"] = ast.unparse(node.returns)
        for arg in node.args.args:
            if arg.annotation:
                hints[arg.arg] = ast.unparse(arg.annotation)
        doc = ast.get_docstring(node) or ""
        self._symbols.append(TypedSymbol(
            name=node.name, kind="async_function", line=node.lineno,
            type_hints=hints, docstring=doc[:200],
        ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        doc = ast.get_docstring(node) or ""
        bases = [ast.unparse(b) for b in node.bases]
        self._symbols.append(TypedSymbol(
            name=node.name, kind="class", line=node.lineno,
            type_hints={"bases": ", ".join(bases)} if bases else {},
            docstring=doc[:200],
        ))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._symbols.append(TypedSymbol(
                name=node.target.id, kind="variable", line=node.lineno,
                type_hints={"type": ast.unparse(node.annotation)},
            ))
        self.generic_visit(node)


def is_module_eligible(filepath: str, allowlist: set[str] | None = None) -> bool:
    """Check if a Python module is in the static-analysis allowlist."""
    if os.environ.get("LIMA_STATIC_ANALYSIS", "0") != "1":
        return False
    if allowlist is None:
        allowlist = _default_allowlist()
    basename = os.path.basename(filepath)
    return basename in allowlist


def _default_allowlist() -> set[str]:
    return {
        "routing_engine.py", "router_v3.py", "http_caller.py",
        "health_tracker.py", "backends.py", "key_pool.py",
    }
