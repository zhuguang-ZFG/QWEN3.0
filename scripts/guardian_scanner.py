"""Core file scanner for lima_guardian."""

from __future__ import annotations

import ast
import hashlib
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scripts.guardian_test_index import find_test_file

from scripts.repo_root import repo_root

PROJECT = repo_root()
CODEGRAPH_DB = str(PROJECT / ".codegraph" / "codegraph.db")

log = logging.getLogger(__name__)

CORE_SCAN_DIRS = (
    "routes",
    "device_gateway",
    "context_pipeline",
    "routing_selector",
    "backends_registry",
    "device_intelligence",
    "device_ota",
    "device_voice",
    "device_memory",
    "device_ledger",
    "device_logic",
    "device_support",
    "device_policy",
    "device_workflow",
    "session_memory",
    "search_gateway",
    "observability",
    "fleet",
    "provider_automation",
    "provider_inventory",
    "response_cleaner",
    "local_retrieval",
    "lima_mcp_stdio",
    "tool_gateway",
)


class CodeScanner:
    """对指定文件执行全谱分析"""

    @staticmethod
    def scan_file(file_path: Path) -> list:
        findings = []
        try:
            source = file_path.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError) as e:
            findings.append(_finding("parse_error", file_path, f"无法解析: {e}"))
            return findings

        rel = _project_rel(file_path)
        functions = _extract_functions(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    _check_import(node.module, rel, findings, file_path)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    _check_import(alias.name, rel, findings, file_path)

        rel_norm = _normalize_rel_path(rel)
        if rel_norm.startswith("routes/") and rel_norm != "routes/route_registry.py":
            routes = _extract_routes(tree)
            if routes and not _check_route_registration(rel_norm):
                for method, path, line in routes:
                    findings.append(
                        _finding("route_unregistered", file_path, f"未注册路由: @router.{method}('{path}')", line=line)
                    )

        if not rel.startswith("tests") and not rel_norm.endswith("__init__.py"):
            if not find_test_file(rel):
                public_funcs = [f for f in functions if not f.name.startswith("_")]
                if public_funcs and not rel.startswith("scripts"):
                    findings.append(
                        _finding(
                            "no_test_file",
                            file_path,
                            f"无测试文件 ({len(public_funcs)} 个公开函数未覆盖)",
                            severity="warning",
                        )
                    )

        for fn in functions:
            if fn.end_lineno and (fn.end_lineno - fn.lineno) > 60:
                findings.append(
                    _finding(
                        "long_function",
                        file_path,
                        f"函数 {fn.name} 过长 ({fn.end_lineno - fn.lineno} 行)",
                        line=fn.lineno,
                        severity="info",
                    )
                )

        if os.path.exists(CODEGRAPH_DB):
            _check_dangling_refs(rel, findings)

        return findings


def _extract_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node)
            sig = _get_signature(node)
            setattr(node, "_sig_hash", hashlib.md5(sig.encode()).hexdigest()[:8])
    return functions


def _finding(finding_type: str, file_path: Path, message: str, line: int = 0, severity: str = "error") -> dict:
    rel = _project_rel(file_path) if file_path else ""
    return {
        "id": hashlib.md5(f"{rel}:{finding_type}:{line}".encode()).hexdigest()[:12],
        "type": finding_type,
        "file": rel,
        "line": line,
        "severity": severity,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "notified": False,
    }


def _get_signature(node: ast.FunctionDef) -> str:
    args = [a.arg for a in node.args.args] if node.args.args else []
    return f"{node.name}({','.join(args)})"


def _check_import(module_name: str, source_file: str, findings: list, file_path: Path):
    if module_name.startswith("."):
        parts = source_file.replace(".py", "").split(os.sep)
        dots = len(module_name) - len(module_name.lstrip("."))
        rel_path = module_name.lstrip(".")
        base = parts[:-dots] if dots > 0 else parts[:-1]
        try_path = os.sep.join(base + rel_path.split(".")) + ".py"
        full = PROJECT / try_path
    else:
        try_path = module_name.replace(".", os.sep) + ".py"
        full = PROJECT / try_path

    if not full.exists() and not module_name.startswith("__future__"):
        pkg = full.with_name(module_name.split(".")[-1])
        if not (pkg.is_dir() and (pkg / "__init__.py").exists()):
            std_lib_dirs = ["site-packages", "Lib", "lib/python"]
            if not any(d in str(full).lower() for d in std_lib_dirs):
                pass


def _extract_routes(tree: ast.AST) -> list:
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and hasattr(dec.func, "attr"):
                    method = dec.func.attr.upper()
                    if method in ("GET", "POST", "PUT", "DELETE", "WS"):
                        if dec.args:
                            path = (
                                ast.literal_eval(dec.args[0])
                                if isinstance(dec.args[0], ast.Constant)
                                else str(dec.args[0])
                            )
                            routes.append((method, path, node.lineno))
    return routes


def _normalize_rel_path(file_rel: str) -> str:
    return file_rel.replace("\\", "/")


def _project_rel(file_path: Path) -> str:
    try:
        return str(file_path.relative_to(PROJECT))
    except ValueError:
        normalized = _normalize_rel_path(str(file_path))
        marker = "routes/"
        idx = normalized.find(marker)
        if idx >= 0:
            return normalized[idx:]
        return normalized


def _check_route_registration(file_rel: str) -> bool | str:
    registry_path = PROJECT / "routes" / "route_registry.py"
    if not registry_path.exists():
        return False
    try:
        content = registry_path.read_text("utf-8", errors="replace")
    except OSError:
        return False

    rel = _normalize_rel_path(file_rel)
    module_name = rel.replace(".py", "").replace("/", ".")
    if module_name in content:
        return module_name

    file_stem = Path(rel).stem
    if f"{file_stem}.router" in content or f'"{file_stem}"' in content:
        return file_stem

    parts = rel.split("/")
    if len(parts) < 3 or parts[0] != "routes":
        return False

    package_module = ".".join(parts[:-1])
    submodule = file_stem
    if package_module not in content:
        return False

    parent_candidates = [
        PROJECT / "/".join(parts[:-1]) / f"{parts[-2]}.py",
        PROJECT / "/".join(parts[:-1]) / "__init__.py",
    ]
    include_markers = (
        f"include_router({submodule}.router",
        f"include_router({submodule}.router)",
        f"from routes.{parts[1]} import {submodule}",
        f"import {submodule}",
    )
    for parent_file in parent_candidates:
        if not parent_file.is_file():
            continue
        try:
            parent_content = parent_file.read_text("utf-8", errors="replace")
        except OSError:
            continue
        if "include_router" in parent_content and any(marker in parent_content for marker in include_markers):
            return module_name
    return False


def _check_dangling_refs(file_rel: str, findings: list):
    pass


class FullScanner:
    @staticmethod
    def scan(modules: list[str] | None = None) -> dict:
        all_findings: dict[str, list] = defaultdict(list)
        paths = [PROJECT / m for m in modules] if modules else [PROJECT / d for d in CORE_SCAN_DIRS]

        scanned = 0
        for path in paths:
            if path.is_dir():
                for py_file in sorted(path.rglob("*.py")):
                    if py_file.name == "__init__.py":
                        continue
                    if "site-packages" in str(py_file) or ".venv" in str(py_file):
                        continue
                    if "esp32" in str(py_file).lower():
                        continue
                    for f in CodeScanner.scan_file(py_file):
                        all_findings[f["type"]].append(f)
                    scanned += 1
            elif path.is_file() and path.suffix == ".py":
                for f in CodeScanner.scan_file(path):
                    all_findings[f["type"]].append(f)
                scanned += 1

        errors, warnings, infos = [], [], []
        for flist in all_findings.values():
            for f in flist:
                if f["severity"] == "error":
                    errors.append(f)
                elif f["severity"] == "warning":
                    warnings.append(f)
                else:
                    infos.append(f)

        return {
            "scanned": scanned,
            "total_findings": len(errors) + len(warnings) + len(infos),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "by_type": {k: len(v) for k, v in all_findings.items()},
            "timestamp": datetime.now().isoformat(),
        }
