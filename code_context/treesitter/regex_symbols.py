from __future__ import annotations

import re

from code_context.ast_adapter import RelationInfo, SymbolInfo


_CLASS_PATTERNS: dict[str, list[str]] = {
    "python": [r"class\s+(\w+)"],
    "javascript": [r"(?:export\s+)?class\s+(\w+)"],
    "typescript": [r"(?:export\s+)?class\s+(\w+)"],
    "go": [r"type\s+(\w+)\s+struct"],
    "rust": [r"(?:pub\s+)?struct\s+(\w+)", r"(?:pub\s+)?enum\s+(\w+)"],
    "c": [r"(?:class|struct)\s+(\w+)"],
    "cpp": [r"(?:class|struct)\s+(\w+)"],
    "java": [r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)"],
}

_FUNCTION_PATTERNS: dict[str, list[str]] = {
    "python": [r"(?:async\s+)?def\s+(\w+)"],
    "javascript": [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
    ],
    "typescript": [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
    ],
    "go": [r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\("],
    "rust": [r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"],
    "c": [r"(?:static\s+|extern\s+|inline\s+)*\w+[\s\*]+(\w+)\s*\("],
    "cpp": [r"(?:static\s+|extern\s+|inline\s+)*\w+[\s\*]+(\w+)\s*\("],
    "java": [r"(?:public|private|protected|static|\s)+\w+[\s<>\w,]*\s+(\w+)\s*\("],
}


def _scan_patterns(lines: list[str], patterns: list[str], kind: str) -> list[tuple[int, str, str]]:
    compiled = [re.compile(p) for p in patterns]
    results: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for pat in compiled:
            m = pat.match(stripped)
            if m:
                results.append((i, m.group(1), kind))
                break
    return results


def _collect_class_blocks(lines: list[str], lang: str) -> list[tuple[int, str, str]]:
    results = _scan_patterns(lines, _CLASS_PATTERNS.get(lang, []), "class")
    if lang != "java":
        return results
    func_pat = re.compile(_FUNCTION_PATTERNS["java"][0])
    skip = {
        i
        for i, line in enumerate(lines, 1)
        if ("class " in line.strip() or "interface " in line.strip()) and func_pat.match(line.strip())
    }
    return [(ln, name, kind) for ln, name, kind in results if ln not in skip]


def _collect_function_blocks(lines: list[str], lang: str) -> list[tuple[int, str, str]]:
    results = _scan_patterns(lines, _FUNCTION_PATTERNS.get(lang, []), "function")
    if lang in ("c", "cpp"):
        results = [(ln, name, kind) for ln, name, kind in results if not lines[ln - 1].strip().startswith(("//", "/*"))]
    if lang == "java":
        results = [
            (ln, name, kind)
            for ln, name, kind in results
            if "class " not in lines[ln - 1].strip() and "interface " not in lines[ln - 1].strip()
        ]
    return results


def _deduplicate_symbols(symbols: list[tuple[int, str, str]]) -> list[dict]:
    seen: set[tuple[str, str, int]] = set()
    out: list[dict] = []
    for line, name, kind in symbols:
        key = (name, kind, line)
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "kind": kind, "line": line})
    return out


def _extract_regex_symbols(source: str, lang: str) -> list[SymbolInfo]:
    lines = source.split("\n")
    symbols = _collect_class_blocks(lines, lang) + _collect_function_blocks(lines, lang)
    symbols.sort(key=lambda t: (t[0], 0 if t[2] == "function" else 1))
    deduped = _deduplicate_symbols(symbols)
    return [SymbolInfo(item["name"], item["kind"], item["line"]) for item in deduped]


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
