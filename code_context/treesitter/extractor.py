from __future__ import annotations

from pathlib import Path

from code_context.ast_adapter import AstExtractor, FileAst, RelationInfo, SymbolInfo
from code_context.treesitter.constants import _EXT_MAP, _detect_language
from code_context.treesitter.parser_pool import ParserPool
from code_context.treesitter.regex_symbols import _extract_regex_relations, _extract_regex_symbols
from code_context.treesitter.ts_symbols import _extract_ts_symbols


class TreeSitterExtractor(AstExtractor):
    """Tree-sitter backed multi-language AST extractor.

    Uses tree-sitter when available, falls back to regex-based extraction
    for common patterns when tree-sitter is not installed.
    """

    _SUPPORTED = frozenset(_EXT_MAP.values())

    def __init__(self) -> None:
        self._parser_pool = ParserPool()
        self._use_tree_sitter = self._parser_pool.use_tree_sitter
        self._parsers = self._parser_pool.parsers

    def extract_symbols(self, file_path: Path) -> list[SymbolInfo]:
        lang = _detect_language(file_path)
        if not lang:
            return []
        try:
            source = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        if lang == "python" and self._use_tree_sitter and "python" in self._parsers:
            return _extract_ts_symbols(source, lang, self._parsers)
        return _extract_regex_symbols(source, lang)

    def extract_relations(
        self,
        file_path: Path,
        module_map: dict[str, str] | None = None,
    ) -> list[RelationInfo]:
        lang = _detect_language(file_path)
        if not lang:
            return []
        try:
            source = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        return _extract_regex_relations(source, lang, file_path.name)

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


def get_tree_sitter_extractor() -> TreeSitterExtractor:
    """Factory: returns a TreeSitterExtractor (always available, degrades gracefully)."""
    return TreeSitterExtractor()
