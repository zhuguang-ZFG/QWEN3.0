"""Test coverage lookup for lima_guardian (import scan + contract tests)."""

from __future__ import annotations

import ast
import os
from functools import lru_cache
from pathlib import Path

PROJECT = Path("D:/QWEN3.0")
TEST_DIR = PROJECT / "tests"
ROUTES_CONTRACT_TEST = "tests/test_routes_auth_contract.py"


def _normalize_rel_path(file_rel: str) -> str:
    return file_rel.replace("\\", "/")


def _module_from_source(source_rel: str) -> str:
    return _normalize_rel_path(source_rel).replace(".py", "").replace("/", ".")


def _imports_from_test(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            parts = node.module.split(".")
            for i in range(1, len(parts) + 1):
                modules.add(".".join(parts[:i]))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                modules.add(name)
                parts = name.split(".")
                for i in range(1, len(parts) + 1):
                    modules.add(".".join(parts[:i]))
    return modules


def _filename_covers_source(test_name: str, source_rel: str) -> bool:
    norm = _normalize_rel_path(source_rel)
    stem = Path(norm).stem
    parts = norm.replace(".py", "").split("/")
    if len(parts) < 2:
        return False
    top = parts[0]
    inner = parts[1] if len(parts) > 2 else stem
    compact = test_name.replace("test_", "").replace("_", "")
    targets = {top.replace("_", ""), inner.replace("_", ""), stem.replace("_", "")}
    return any(t and t in compact for t in targets)


@lru_cache(maxsize=1)
def _module_import_tests() -> dict[str, list[str]]:
    by_module: dict[str, list[str]] = {}
    if not TEST_DIR.is_dir():
        return by_module
    for py_file in sorted(TEST_DIR.rglob("*.py")):
        if not py_file.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(py_file.read_text("utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        rel_test = str(py_file.relative_to(PROJECT))
        for mod in _imports_from_test(tree):
            by_module.setdefault(mod, []).append(rel_test)
    return by_module


@lru_cache(maxsize=1)
def _all_test_files() -> list[str]:
    if not TEST_DIR.is_dir():
        return []
    return sorted(str(p.relative_to(PROJECT)) for p in TEST_DIR.rglob("*.py") if p.name.startswith("test_"))


def _source_has_route_decorators(py_file: Path) -> bool:
    try:
        tree = ast.parse(py_file.read_text("utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and hasattr(dec.func, "attr"):
                if dec.func.attr.upper() in ("GET", "POST", "PUT", "DELETE", "WS", "PATCH", "WEBSOCKET"):
                    return True
    return False


def find_test_file(source_rel: str) -> str | None:
    """Return a test file that covers source_rel, or None."""
    norm = _normalize_rel_path(source_rel)
    if norm.startswith("tests/") or norm.endswith("__init__.py"):
        return ROUTES_CONTRACT_TEST

    stem = norm.replace(".py", "").replace("/", "_")
    candidates = [
        TEST_DIR / f"test_{stem.replace('routes_', '')}.py",
        TEST_DIR / f"test_{norm.replace('.py', '').replace('/', '_')}.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.relative_to(PROJECT))

    module = _module_from_source(norm)
    parts = module.split(".")
    import_map = _module_import_tests()
    # ponytail: skip bare top-level package keys (e.g. "routes") — too many false positives
    for i in range(len(parts), 1, -1):
        tests = import_map.get(".".join(parts[:i]))
        if tests:
            return tests[0]

    if norm.startswith("routes/") and norm != "routes/route_registry.py":
        contract = TEST_DIR / "test_routes_auth_contract.py"
        if contract.is_file():
            src = PROJECT / norm.replace("/", os.sep)
            if src.is_file() and _source_has_route_decorators(src):
                return ROUTES_CONTRACT_TEST

    for test_rel in _all_test_files():
        if _filename_covers_source(Path(test_rel).stem, norm):
            return test_rel

    if TEST_DIR.is_dir():
        for name in os.listdir(str(TEST_DIR)):
            if name.endswith(".py") and name.startswith("test_"):
                compact = stem.replace("routes_", "").replace("device_gateway_", "")
                if compact in name:
                    return f"tests/{name}"

    return None


def clear_test_index_cache() -> None:
    """For tests: invalidate cached import scan."""
    _module_import_tests.cache_clear()
    _all_test_files.cache_clear()
