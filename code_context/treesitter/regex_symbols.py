from __future__ import annotations

import re

from code_context.ast_adapter import RelationInfo, SymbolInfo


def _extract_regex_symbols(source: str, lang: str) -> list[SymbolInfo]:
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
    source: str,
    lang: str,
    filename: str,
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
