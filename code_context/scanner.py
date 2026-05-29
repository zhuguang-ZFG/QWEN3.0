from pathlib import Path

from .index_store import CodeSymbol, FileRecord

_LANG_EXT_MAP: dict[str, str] = {
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


def scan_file(path: Path) -> FileRecord:
    """Scan any supported file type using the appropriate extractor."""
    suffix = path.suffix.lower()
    lang = _LANG_EXT_MAP.get(suffix)
    if not lang:
        return FileRecord(path=str(path), mtime=0.0)
    try:
        from .ast_adapter import get_extractor
        extractor = get_extractor(lang)
        if extractor:
            ast = extractor.scan_file(path)
            symbols = [
                CodeSymbol(name=s.name, kind=s.kind, line=s.line)
                for s in ast.symbols
            ]
            imports = [(r.target, r.line) for r in ast.relations if r.relation_type == "imports"]
            return FileRecord(
                path=str(path),
                symbols=sorted(symbols, key=lambda s: (s.line, s.name)),
                imports=sorted(imports, key=lambda item: (item[1], item[0])),
                mtime=path.stat().st_mtime,
            )
    except Exception:
        pass
    return _scan_python_file(path)


def scan_python_file(path: Path) -> FileRecord:
    """Legacy Python-only scan (kept for backward compatibility)."""
    return _scan_python_file(path)


def _scan_python_file(path: Path) -> FileRecord:
    import ast as _ast

    try:
        source = path.read_text(encoding="utf-8")
        tree = _ast.parse(source, filename=str(path))
    except (UnicodeDecodeError, SyntaxError, OSError):
        return FileRecord(path=str(path), mtime=0.0)

    symbols: list[CodeSymbol] = []
    imports: list[tuple[str, int]] = []

    for node in _ast.walk(tree):
        if isinstance(node, _ast.ClassDef):
            symbols.append(CodeSymbol(node.name, "class", node.lineno))
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            symbols.append(CodeSymbol(node.name, "function", node.lineno))
        elif isinstance(node, _ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, _ast.ImportFrom) and node.module:
            for alias in node.names:
                imports.append((f"{node.module}.{alias.name}", node.lineno))

    return FileRecord(
        path=str(path),
        symbols=sorted(symbols, key=lambda s: (s.line, s.name)),
        imports=sorted(imports, key=lambda item: (item[1], item[0])),
        mtime=path.stat().st_mtime,
    )
