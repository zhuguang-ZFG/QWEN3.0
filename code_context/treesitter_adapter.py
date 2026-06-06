"""Multi-language AST extraction via tree-sitter.

Falls back gracefully when tree-sitter is unavailable or has version conflicts.
Supported languages: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from code_context.ast_adapter import (
    AstExtractor,
    FileAst,
    RelationInfo,
    SymbolInfo,
)

_log = logging.getLogger(__name__)

_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

_TS_NODE_KINDS: dict[str, str] = {
    "class_definition": "class",
    "function_definition": "function",
    "async_function_definition": "function",
    "decorated_definition": "function",
    "method_definition": "method",
    "arrow_function": "function",
    "function_declaration": "function",
    "class_declaration": "class",
    "interface_declaration": "class",
    "type_alias_declaration": "class",
    "export_statement": "function",
    "method_definition": "method",
}

_TS_CALLABLE_KINDS = frozenset({
    "function", "method", "arrow_function",
})

_TS_IMPORT_NODE_TYPES = frozenset({
    "import_statement",
    "import_declaration",
    "import_from_statement",
    "import_specifier",
    "import_alias",
    "required_import",
    "import_specifier",
    "package_clause",
})

_TS_EXTENDS_TYPES = frozenset({
    "class_heritage",
    "superclass",
    "base_class",
})

_TREE_SITTER_AVAILABLE: bool | None = None


def _check_tree_sitter() -> bool:
    global _TREE_SITTER_AVAILABLE
    if _TREE_SITTER_AVAILABLE is not None:
        return _TREE_SITTER_AVAILABLE
    try:
        from tree_sitter_languages import get_parser
        get_parser("python")
        _TREE_SITTER_AVAILABLE = True
    except Exception as exc:
        _log.warning("operation failed: %s", exc)
        _TREE_SITTER_AVAILABLE = False
        _log.debug("tree-sitter unavailable, using regex fallback")
    return _TREE_SITTER_AVAILABLE


def _detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return _EXT_MAP.get(suffix, "")


def _extract_name_from_text(source: str, node_type: str, start_line: int) -> str:
    lines = source.split("\n")
    if start_line >= len(lines):
        return ""
    line = lines[start_line]
    if node_type in ("function_definition", "async_function_definition"):
        m = re.search(r"(?:async\s+)?def\s+(\w+)", line)
        return m.group(1) if m else ""
    if node_type == "class_definition":
        m = re.search(r"class\s+(\w+)", line)
        return m.group(1) if m else ""
    return ""


class TreeSitterExtractor(AstExtractor):
    """Tree-sitter backed multi-language AST extractor.

    Uses tree-sitter when available, falls back to regex-based extraction
    for common patterns when tree-sitter is not installed.
    """

    _SUPPORTED = frozenset(_EXT_MAP.values())

    def __init__(self) -> None:
        self._use_tree_sitter = _check_tree_sitter()
        self._parsers: dict[str, object] = {}
        if self._use_tree_sitter:
            self._init_parsers()

    def _init_parsers(self) -> None:
        try:
            from tree_sitter_languages import get_parser
            for lang_name in ("python", "javascript", "typescript", "go", "rust", "java", "c"):
                try:
                    self._parsers[lang_name] = get_parser(lang_name)
                except Exception as exc:
                    _log.warning("operation failed: %s", exc)
                    _log.debug("tree-sitter parser unavailable for %s", lang_name)
        except ImportError:
            self._use_tree_sitter = False

    def extract_symbols(self, file_path: Path) -> list[SymbolInfo]:
        lang = _detect_language(file_path)
        if not lang:
            return []
        try:
            source = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        if lang == "python" and self._use_tree_sitter and "python" in self._parsers:
            return self._extract_ts_symbols(source, lang)
        return self._extract_regex_symbols(source, lang)

    def extract_relations(
        self, file_path: Path, module_map: dict[str, str] | None = None,
    ) -> list[RelationInfo]:
        lang = _detect_language(file_path)
        if not lang:
            return []
        try:
            source = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        return self._extract_regex_relations(source, lang, file_path.name)

    def scan_file(self, file_path: Path) -> FileAst:
        symbols = self.extract_symbols(file_path)
        relations = self.extract_relations(file_path)
        return FileAst(
            path=str(file_path),
            symbols=symbols,
            relations=relations,
            language=_detect_language(file_path),
        )

    @property
    def supported_languages(self) -> frozenset[str]:
        return self._SUPPORTED

    def _extract_ts_symbols(self, source: str, lang: str) -> list[SymbolInfo]:
        parser = self._parsers.get(lang)
        if not parser:
            return self._extract_regex_symbols(source, lang)
        try:
            tree = parser.parse(source.encode("utf-8"))
            symbols: list[SymbolInfo] = []
            self._walk_ts_node(tree.root_node, symbols, source, depth=0)
            return symbols
        except Exception as exc:
            _log.warning("operation failed: %s", exc)
            return self._extract_regex_symbols(source, lang)

    def _walk_ts_node(
        self, node: object, symbols: list[SymbolInfo], source: str, depth: int,
    ) -> None:
        if depth > 20:
            return
        node_type = getattr(node, "type", "")
        kind = _TS_NODE_KINDS.get(node_type)
        if kind:
            name = self._get_ts_node_name(node, source)
            line = getattr(node, "start_point", (0, 0))[0] + 1
            if name:
                symbols.append(SymbolInfo(name=name, kind=kind, line=line))
        for child in getattr(node, "children", []):
            self._walk_ts_node(child, symbols, source, depth + 1)

    def _get_ts_node_name(self, node: object, source: str) -> str:
        for child in getattr(node, "children", []):
            child_type = getattr(child, "type", "")
            if child_type in ("identifier", "name", "field_identifier", "property_identifier"):
                start = getattr(child, "start_point", (0, 0))
                end = getattr(child, "end_point", (0, 0))
                lines = source.split("\n")
                if start[0] < len(lines):
                    line_text = lines[start[0]]
                    return line_text[start[1]:end[1]]
        return ""

    def _extract_regex_symbols(self, source: str, lang: str) -> list[SymbolInfo]:
        symbols: list[SymbolInfo] = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if lang == "python":
                m = re.match(r"(?:async\s+)?def\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"class\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
            elif lang in ("javascript", "typescript"):
                m = re.match(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"(?:export\s+)?class\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
                m = re.match(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
            elif lang == "go":
                m = re.match(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\(", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"type\s+(\w+)\s+struct", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
            elif lang == "rust":
                m = re.match(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"(?:pub\s+)?struct\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
                m = re.match(r"(?:pub\s+)?enum\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
            elif lang in ("c", "cpp"):
                m = re.match(r"(?:static\s+|extern\s+|inline\s+)*\w+[\s\*]+(\w+)\s*\(", stripped)
                if m and not stripped.startswith("//") and not stripped.startswith("/*"):
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"(?:class|struct)\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
            elif lang == "java":
                m = re.match(r"(?:public|private|protected|static|\s)+\w+[\s<>\w,]*\s+(\w+)\s*\(", stripped)
                if m and "class " not in stripped and "interface " not in stripped:
                    symbols.append(SymbolInfo(m.group(1), "function", i))
                    continue
                m = re.match(r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)", stripped)
                if m:
                    symbols.append(SymbolInfo(m.group(1), "class", i))
                    continue
        return symbols

    def _extract_regex_relations(
        self, source: str, lang: str, filename: str,
    ) -> list[RelationInfo]:
        relations: list[RelationInfo] = []
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if lang == "python":
                m = re.match(r"from\s+([\w.]+)\s+import", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
                m = re.match(r"import\s+([\w.]+)", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
            elif lang in ("javascript", "typescript"):
                m = re.match(r"""(?:import|from)\s+.*?["'](.+?)["']""", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
                m = re.match(r"""require\s*\(\s*["'](.+?)["']""", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
            elif lang == "go":
                m = re.match(r'"(.+?)"', stripped)
                if stripped.startswith("import") and m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
            elif lang == "rust":
                m = re.match(r"(?:extern\s+crate|use)\s+([\w:]+)", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
            elif lang in ("java",):
                m = re.match(r"import\s+([\w.]+)", stripped)
                if m:
                    relations.append(RelationInfo(filename, m.group(1), "imports", i))
                    continue
        return relations


def get_tree_sitter_extractor() -> TreeSitterExtractor:
    """Factory: returns a TreeSitterExtractor (always available, degrades gracefully)."""
    return TreeSitterExtractor()
