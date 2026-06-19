from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

_TREE_SITTER_AVAILABLE: bool | None = None


def _check_tree_sitter() -> bool:
    global _TREE_SITTER_AVAILABLE
    if _TREE_SITTER_AVAILABLE is not None:
        return _TREE_SITTER_AVAILABLE
    try:
        from tree_sitter_languages import get_parser

        get_parser("python")
        _TREE_SITTER_AVAILABLE = True
    except Exception:
        _TREE_SITTER_AVAILABLE = False
        _log.debug("tree-sitter unavailable, using regex fallback")
    return _TREE_SITTER_AVAILABLE


class ParserPool:
    """Lazy initialised pool of tree-sitter parsers."""

    def __init__(self) -> None:
        self._use_tree_sitter = _check_tree_sitter()
        self._parsers: dict[str, object] = {}
        if self._use_tree_sitter:
            self._init_parsers()

    @property
    def use_tree_sitter(self) -> bool:
        return self._use_tree_sitter

    @property
    def parsers(self) -> dict[str, object]:
        return self._parsers

    def _init_parsers(self) -> None:
        try:
            from tree_sitter_languages import get_parser

            for lang_name in (
                "python",
                "javascript",
                "typescript",
                "go",
                "rust",
                "java",
                "c",
            ):
                try:
                    self._parsers[lang_name] = get_parser(lang_name)
                except Exception:
                    _log.debug("tree-sitter parser unavailable for %s", lang_name)
        except ImportError:
            self._use_tree_sitter = False
