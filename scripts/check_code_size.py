"""Check Python file and function size against LiMa/ECC constraints.

Constraints:
- Single file target: <= 300 lines
- Single function target: <= 50 lines

Exit codes:
- 0: all checks passed
- 1: file or function size violations found
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections.abc import Callable
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
    ".agent",
    ".codebuddy",
    ".codex",
    ".continue",
    ".cursor",
    ".gemini",
    ".github",
    ".kiro",
    ".opencode",
    ".qoder",
    ".roo",
    ".trae",
    ".windsurf",
    "provider-probe-offline",
    "data",
    "tmp",
}


def _should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def _iter_python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if not _should_skip(p)]


def _iter_git_python_files(root: Path) -> list[Path]:
    """List Python files known to git (tracked or staged)."""
    try:
        output = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "*.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _iter_python_files(root)

    files: list[Path] = []
    for line in output.splitlines():
        path = root / line
        if path.exists() and not _should_skip(path):
            files.append(path)
    return files


def _count_function_lines(node: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]) -> int:
    """Return the number of source lines spanning a function definition."""
    start = node.lineno
    end = node.end_lineno or start
    return end - start + 1


def check_files(
    root: Path,
    file_iterator: Callable[[Path], list[Path]] = _iter_python_files,
    file_limit: int = FILE_LIMIT,
) -> list[tuple[Path, int]]:
    violations = []
    for path in file_iterator(root):
        line_count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if line_count > file_limit:
            violations.append((path, line_count))
    violations.sort(key=lambda item: item[1], reverse=True)
    return violations


def check_functions(
    root: Path,
    file_iterator: Callable[[Path], list[Path]] = _iter_python_files,
    func_limit: int = FUNC_LIMIT,
) -> list[tuple[Path, str, int]]:
    violations = []
    for path in file_iterator(root):
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


def _iter_explicit_paths(root: Path, paths: list[str]) -> list[Path]:
    """Resolve explicit relative paths to existing Python files under root."""
    result: list[Path] = []
    for raw in paths:
        path = root / raw
        if path.exists() and path.suffix == ".py" and not _should_skip(path):
            result.append(path)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Python file/function size constraints.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Python files to check; defaults to all Python files under root",
    )
    parser.add_argument(
        "--git-tracked",
        action="store_true",
        help="Only check Python files known to git (tracked or staged).",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.paths:
        file_iterator = lambda r: _iter_explicit_paths(r, args.paths)  # noqa: E731
    elif args.git_tracked:
        file_iterator = _iter_git_python_files
    else:
        file_iterator = _iter_python_files
    file_violations = check_files(root, file_iterator)
    func_violations = check_functions(root, file_iterator)

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
