"""Helpers for scripts/deploy_unified.py.

Keeps the deploy script itself focused while providing dependency-aware
partial deploys and early crash detection.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


def _module_name_from_path(path: Path, project_root: Path) -> str:
    """Convert a project file path to its dotted module name."""
    rel = path.resolve().relative_to(project_root.resolve())
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join(parts)


def _top_level_imports(path: Path, project_root: Path) -> list[str]:
    """Return top-level absolute module names imported by a Python file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    current_module = _module_name_from_path(path, project_root)
    # For __init__.py, the package is the module itself; otherwise drop the final segment.
    current_package = current_module if path.name == "__init__.py" else ".".join(current_module.split(".")[:-1])

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                module = node.module
            elif node.level > 0:
                # Resolve relative import to absolute module name.
                # level=1 keeps the whole current package; each extra dot goes up one level.
                package_parts = current_package.split(".")
                drop = node.level - 1
                if drop > len(package_parts):
                    continue
                base = ".".join(package_parts[:-drop]) if drop else current_package
                if node.module:
                    module = f"{base}.{node.module}" if base else node.module
                else:
                    module = base
            else:
                continue
            names.append(module)
    return names


def _resolve_local_module(name: str, project_root: Path) -> Path | None:
    """Find the local file backing a module name, if any."""
    top = name.split(".")[0]
    if top in sys.stdlib_module_names:
        return None
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    origin = Path(spec.origin).resolve()
    try:
        origin.relative_to(project_root.resolve())
    except ValueError:
        return None
    return origin


def expand_with_dependencies(
    files: list[str],
    project_root: Path,
    *,
    exclude_patterns: tuple[str, ...] = ("tests/", "scripts/", "docs/", "infra/"),
) -> list[str]:
    """Expand a file list with any local modules they import.

    This prevents partial deploys from crashing the VPS because a newly split
    helper module was not uploaded together with the changed file.
    """
    project_root = project_root.resolve()
    seen: set[str] = set()
    result: list[str] = []
    stack = list(files)

    def _add(rel: str) -> None:
        rel = rel.replace("\\", "/")
        if rel in seen:
            return
        seen.add(rel)
        result.append(rel)
        stack.append(rel)

    for f in files:
        _add(f)

    while stack:
        current = stack.pop()
        current_path = project_root / current
        if not current_path.suffix == ".py":
            continue
        for mod in _top_level_imports(current_path, project_root):
            origin = _resolve_local_module(mod, project_root)
            if origin is None:
                continue
            rel = origin.relative_to(project_root).as_posix()
            if any(rel.startswith(p) for p in exclude_patterns):
                continue
            _add(rel)

    return list(dict.fromkeys(result))
