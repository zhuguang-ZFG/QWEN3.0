"""Test coverage analysis using AST introspection."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT = Path("D:/QWEN3.0")

# LiMa 核心模块
CORE_MODULES = [
    ("routes", "FastAPI 路由"),
    ("device_gateway", "设备网关"),
    ("context_pipeline", "上下文管线"),
    ("routing_selector", "路由选择"),
    ("backends_registry", "后端注册表"),
    ("routing_loop", "路由循环"),
    ("routing_ml", "路由机器学习"),
    ("device_intelligence", "设备智能"),
    ("device_voice", "设备语音"),
    ("device_memory", "设备记忆"),
    ("device_ota", "OTA 升级"),
    ("device_ledger", "设备账本"),
    ("device_logic", "设备逻辑"),
    ("device_support", "设备支持"),
    ("device_policy", "设备策略"),
    ("device_workflow", "设备工作流"),
    ("session_memory", "会话记忆"),
    ("observability", "可观测性"),
    ("fleet", "车队管理"),
    ("provider_automation", "提供商自动化"),
    ("provider_inventory", "提供商清单"),
    ("provider_probe", "提供商探针"),
    ("response_cleaner", "响应清洗"),
    ("local_retrieval", "本地检索"),
    ("external_enrichment", "外部丰富"),
    ("lima_mcp_stdio", "MCP 服务器"),
    ("tool_gateway", "工具网关"),
]


def get_all_functions(module_dir: str) -> list:
    """从模块目录提取所有公开函数/方法"""
    functions = []
    mod_path = PROJECT / module_dir
    if not mod_path.is_dir():
        return functions

    for py_file in sorted(mod_path.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        try:
            source = py_file.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        rel = str(py_file.relative_to(PROJECT))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 只记公开函数（非 _ 开头）
                if not node.name.startswith("_"):
                    functions.append(
                        {
                            "name": node.name,
                            "file": rel,
                            "line": node.lineno,
                        }
                    )

    return functions


def get_test_files_importing_module() -> dict[str, list[str]]:
    """Map module name -> test files that import it (AST import scan)."""
    test_dir = PROJECT / "tests"
    by_module: dict[str, set[str]] = defaultdict(set)
    if not test_dir.is_dir():
        return {}

    for py_file in test_dir.rglob("*.py"):
        if not py_file.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(py_file.read_text("utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        rel = str(py_file.relative_to(PROJECT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                by_module[root].add(rel)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    by_module[alias.name.split(".")[0]].add(rel)
    return {k: sorted(v) for k, v in by_module.items()}


def get_test_functions() -> dict:
    """从测试文件提取所有测试函数，按关联模块组织"""
    test_dir = PROJECT / "tests"
    if not test_dir.is_dir():
        return {}

    tests_by_module = defaultdict(list)

    # 递归遍历 tests/ 目录
    for py_file in test_dir.rglob("*.py"):
        if py_file.name.startswith("test_"):
            try:
                source = py_file.read_text("utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, OSError):
                continue

            rel = str(py_file.relative_to(PROJECT))
            test_funcs = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        test_funcs.append(node.name)

            # 从测试文件名推断关联模块
            # test_device_gateway_xxx.py -> device_gateway
            # test_context_pipeline_xxx.py -> context_pipeline
            fname = py_file.stem  # without .py
            matched = None
            for mod_name, _ in CORE_MODULES:
                if mod_name.replace("_", "") in fname.replace("test_", "").replace("_", ""):
                    matched = mod_name
                    break

            key = matched or fname.replace("test_", "")
            tests_by_module[key].extend(test_funcs)

    return dict(tests_by_module)


def analyze(module_filter: str | None = None) -> dict[str, Any]:
    """分析测试覆盖"""
    all_results = {}
    tests_by_mod = get_test_functions()
    import_tests = get_test_files_importing_module()

    for mod_name, mod_desc in CORE_MODULES:
        if module_filter and module_filter not in mod_name:
            continue

        functions = get_all_functions(mod_name)
        if not functions:
            continue

        if mod_name in tests_by_mod:
            test_funcs = tests_by_mod[mod_name]
            # 匹配：检查测试函数是否包含源码函数名
            covered = []
            uncovered = []
            for fn in functions:
                fn_lower = fn["name"].lower()
                matched = False
                for tf in test_funcs:
                    if fn_lower in tf.lower() or tf.lower().replace("test_", "") in fn_lower:
                        matched = True
                        break
                if matched:
                    covered.append(fn)
                else:
                    uncovered.append(fn)
        else:
            covered = []
            uncovered = functions

        all_results[mod_name] = {
            "description": mod_desc,
            "total": len(functions),
            "covered": len(covered),
            "uncovered": len(uncovered),
            "rate": round(len(covered) / len(functions) * 100, 1) if functions else 0,
            "uncovered_list": uncovered[:20],
            "test_files": import_tests.get(mod_name, []),
            "test_file_count": len(import_tests.get(mod_name, [])),
            "name_matched_tests": len(tests_by_mod.get(mod_name, [])),
        }

    return all_results
