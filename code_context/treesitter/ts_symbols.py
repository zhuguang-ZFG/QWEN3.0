from __future__ import annotations

import re

from code_context.ast_adapter import SymbolInfo
from code_context.treesitter.constants import _TS_NODE_KINDS
from code_context.treesitter.regex_symbols import _extract_regex_symbols


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


def _extract_ts_symbols(
    source: str,
    lang: str,
    parsers: dict[str, object],
) -> list[SymbolInfo]:
    parser = parsers.get(lang)
    if not parser:
        return _extract_regex_symbols(source, lang)
    try:
        tree = parser.parse(source.encode("utf-8"))
        symbols: list[SymbolInfo] = []
        _walk_ts_node(tree.root_node, symbols, source, depth=0)
        return symbols
    except Exception:
        return _extract_regex_symbols(source, lang)


def _walk_ts_node(
    node: object,
    symbols: list[SymbolInfo],
    source: str,
    depth: int,
) -> None:
    if depth > 20:
        return
    node_type = getattr(node, "type", "")
    kind = _TS_NODE_KINDS.get(node_type)
    if kind:
        name = _get_ts_node_name(node, source)
        line = getattr(node, "start_point", (0, 0))[0] + 1
        if name:
            symbols.append(SymbolInfo(name=name, kind=kind, line=line))
    for child in getattr(node, "children", []):
        _walk_ts_node(child, symbols, source, depth + 1)


def _get_ts_node_name(node: object, source: str) -> str:
    for child in getattr(node, "children", []):
        child_type = getattr(child, "type", "")
        if child_type in ("identifier", "name", "field_identifier", "property_identifier"):
            start = getattr(child, "start_point", (0, 0))
            end = getattr(child, "end_point", (0, 0))
            lines = source.split("\n")
            if start[0] < len(lines):
                line_text = lines[start[0]]
                return line_text[start[1] : end[1]]
    return ""
