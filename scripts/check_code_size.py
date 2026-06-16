"""Check Python file and function size against LiMa/ECC constraints.

Constraints:
- Single file target: <= 300 lines
- Single function target: <= 50 lines

Exit codes:
- 0: all checks passed
- 1: file or function size violations found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FILE_LIMIT = 300
FUNC_LIMIT = 50

EXCLUDE_DIRS = {
    ".venv310",
    "__pycache__",
    "node_modules",
    "reference",
    "esp32S_XYZ",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".lima-data",
    ".codegraph",
    ".omc",
    ".omk",
    ".omx",
    ".claude",
    "provider-probe-offline",
    "data",
}


def _should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def _iter_python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if not _should_skip(p)]


def _count_function_lines(node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]) -> int:
    """Return the number of source lines spanning a function definition."""
    start = node.lineno
    end = node.end_lineno or start
    return end - start + 1


def check_files(root: Path, file_limit: int = FILE_LIMIT) -> list[tuple[Path, int]]:
    violations = []
    for path in _iter_python_files(root):
        line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if line_count > file_limit:
            violations.append((path, line_count))
    violations.sort(key=lambda item: item[1], reverse=True)
    return violations


def check_functions(root: Path, func_limit: int = FUNC_LIMIT) -> list[tuple[Path, str, int]]:
    violations = []
    for path in _iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = _count_function_lines(node, source.splitlines())
                if lines > func_limit:
                    name = node.name
                    if isinstance(node, ast.AsyncFunctionDef):
                        name = f"async {name}"
                    violations.append((path, name, lines))
    violations.sort(key=lambda item: item[2], reverse=True)
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    file_violations = check_files(root)
    func_violations = check_functions(root)

    print(f"Checking Python files under {root}")
    print(f"File limit: {FILE_LIMIT} lines, Function limit: {FUNC_LIMIT} lines")
    print()

    if file_violations:
        print(f"Files exceeding {FILE_LIMIT} lines ({len(file_violations)}):")
        for path, count in file_violations:
            print(f"  {count:5d}  {path.relative_to(root)}")
        print()
    else:
        print(f"No files exceed {FILE_LIMIT} lines.")
        print()

    if func_violations:
        # Show top 30 functions to avoid overwhelming output
        shown = func_violations[:30]
        print(f"Functions exceeding {FUNC_LIMIT} lines (top {len(shown)} of {len(func_violations)}):")
        for path, name, count in shown:
            print(f"  {count:5d}  {path.relative_to(root)}::{name}")
        if len(func_violations) > 30:
            print(f"  ... and {len(func_violations) - 30} more")
        print()
    else:
        print(f"No functions exceed {FUNC_LIMIT} lines.")
        print()

    if file_violations or func_violations:
        print("Result: FAIL - size constraints violated.")
        return 1

    print("Result: PASS - all size constraints satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
