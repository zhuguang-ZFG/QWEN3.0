import ast
from pathlib import Path

from .index_store import CodeSymbol, FileRecord


def scan_python_file(path: Path) -> FileRecord:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (UnicodeDecodeError, SyntaxError, OSError):
        return FileRecord(path=str(path), mtime=0.0)

    symbols: list[CodeSymbol] = []
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(CodeSymbol(node.name, "class", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(CodeSymbol(node.name, "function", node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports.append((f"{node.module}.{alias.name}", node.lineno))

    return FileRecord(
        path=str(path),
        symbols=sorted(symbols, key=lambda s: (s.line, s.name)),
        imports=sorted(imports, key=lambda item: (item[1], item[0])),
        mtime=path.stat().st_mtime,
    )
