"""AST Adapter - tree-sitter boundary definition.

Defines the AST extractor protocol without requiring a tree-sitter runtime
dependency. The default implementation uses Python stdlib `ast`.

Interface:
    AstExtractor: abstract base - extract_symbols, extract_relations
    StdlibAstExtractor: Python stdlib `ast` implementation (default)
    (future) TreeSitterExtractor: tree-sitter backed, gated
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SymbolInfo:
    name: str
    kind: str  # "class" | "function" | "method" | "variable"
    line: int
    docstring: str = ""


@dataclass
class RelationInfo:
    source: str
    target: str
    relation_type: str  # "imports" | "calls" | "extends" | "defines_class" | "defines_func"
    line: int = 0


@dataclass
class FileAst:
    path: str
    symbols: list[SymbolInfo] = field(default_factory=list)
    relations: list[RelationInfo] = field(default_factory=list)
    language: str = "python"


class AstExtractor(ABC):
    """Protocol for AST extraction backends.

    Implementations:
        StdlibAstExtractor - Python stdlib (default, no dependencies)
        (future) TreeSitterExtractor - tree-sitter, multi-language, gated
    """

    @abstractmethod
    def extract_symbols(self, file_path: Path) -> list[SymbolInfo]: ...

    @abstractmethod
    def extract_relations(self, file_path: Path, module_map: dict[str, str] | None = None) -> list[RelationInfo]: ...

    @abstractmethod
    def scan_file(self, file_path: Path) -> FileAst: ...

    @property
    @abstractmethod
    def supported_languages(self) -> frozenset[str]: ...


class StdlibAstExtractor(AstExtractor):
    """Python-only AST extractor using stdlib `ast`.

    Gracefully handles SyntaxError and file read errors by returning
    empty results rather than raising.
    """

    _SUPPORTED = frozenset({"python"})

    def extract_symbols(self, file_path: Path) -> list[SymbolInfo]:
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            return []

        symbols: list[SymbolInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                symbols.append(SymbolInfo(node.name, "class", node.lineno, docstring=doc))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                kind = "method" if _is_method(node, tree) else "function"
                symbols.append(SymbolInfo(node.name, kind, node.lineno, docstring=doc))
        return symbols

    def extract_relations(self, file_path: Path, module_map: dict[str, str] | None = None) -> list[RelationInfo]:
        module_map = module_map or {}
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            return []

        fname = str(file_path.name)
        relations: list[RelationInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target_path = _resolve_module_target(alias.name, module_map)
                    if target_path:
                        relations.append(RelationInfo(fname, target_path, "imports", node.lineno))
            elif isinstance(node, ast.ImportFrom) and node.module:
                target_path = _resolve_module_target(node.module, module_map)
                if target_path:
                    relations.append(RelationInfo(fname, target_path, "imports", node.lineno))
            elif isinstance(node, ast.ClassDef):
                relations.append(RelationInfo(fname, node.name, "defines_class", node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "defines_func"
                relations.append(RelationInfo(fname, node.name, kind, node.lineno))
        return relations

    def scan_file(self, file_path: Path) -> FileAst:
        symbols = self.extract_symbols(file_path)
        relations = self.extract_relations(file_path)
        return FileAst(path=str(file_path), symbols=symbols, relations=relations, language="python")

    @property
    def supported_languages(self) -> frozenset[str]:
        return self._SUPPORTED


def _is_method(func_node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module) -> bool:
    """Heuristic: a function inside a ClassDef is a method."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if child is func_node:
                    return True
    return False


def _resolve_module_target(module_name: str, module_map: dict[str, str]) -> str:
    """Resolve an import module name against full, root, and leaf module keys."""
    parts = module_name.split(".")
    candidates = [module_name]
    if parts:
        candidates.append(parts[0])
        candidates.append(parts[-1])
    for candidate in candidates:
        if candidate in module_map:
            return module_map[candidate]
    return ""


def get_extractor(language: str = "python") -> AstExtractor | None:
    """Factory: returns the appropriate AstExtractor for the given language.

    Uses stdlib ast for Python (zero dependencies).
    Falls back to tree-sitter regex adapter for other languages.
    """
    if language == "python":
        return StdlibAstExtractor()
    try:
        from code_context.treesitter_adapter import get_tree_sitter_extractor

        extractor = get_tree_sitter_extractor()
        if language in extractor.supported_languages:
            return extractor
    except Exception as exc:
        _log.debug("code_context/ast_adapter.py: {}", type(exc).__name__)
    return None
