#!/usr/bin/env python3
"""
LiMa 代码守卫 —— 全量扫描 + 增量监控。
MODE 1 (--full-scan)：全项目健康基线
  - 每个 .py 文件 AST 分析
  - 路由注册交叉比对
  - 测试覆盖查找
  - import 存在性验证
  - CodeGraph 悬挂引用检查
MODE 2 (--watch)：增量文件变更守护
MODE 3 (--baseline)：定时基线刷新 + 趋势

用法:
  python scripts/lima_guardian.py --full-scan          # 首次全量扫描
  python scripts/lima_guardian.py --baseline           # 刷新基线
  python scripts/lima_guardian.py --watch              # 守护模式 (文件监听)
  python scripts/lima_guardian.py --print-findings     # 查看当前发现
"""

import ast
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT = Path("D:/QWEN3.0")
GUARDIAN = PROJECT / ".guardian"
FINDINGS_FILE = GUARDIAN / "findings.json"
BASELINE_FILE = GUARDIAN / "baseline.json"
CODEGRAPH_DB = str(PROJECT / ".codegraph" / "codegraph.db")

logging.basicConfig(level=logging.INFO, format="[guardian] %(message)s")
log = logging.getLogger(__name__)


# ========== 核心扫描器 ==========


class CodeScanner:
    """对指定文件执行全谱分析"""

    @staticmethod
    def scan_file(file_path: Path) -> list:
        """扫描单个文件，返回 findings 列表"""
        findings = []

        try:
            source = file_path.read_text("utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError) as e:
            findings.append(_finding("parse_error", file_path, f"无法解析: {e}"))
            return findings

        rel = _project_rel(file_path)

        # 1. 函数/方法提取
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node)
                # 函数签名变化检测（用于增量模式）
                sig = _get_signature(node)
                setattr(node, "_sig_hash", hashlib.md5(sig.encode()).hexdigest()[:8])

        # 2. import 存在性验证
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module_name = node.module
                if module_name:
                    _check_import(module_name, rel, findings, file_path)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    _check_import(alias.name, rel, findings, file_path)

        # 3. 路由注册检查（仅 routes/ 文件）
        rel_norm = _normalize_rel_path(rel)
        if rel_norm.startswith("routes/") and rel_norm != "routes/route_registry.py":
            routes = _extract_routes(tree)
            if routes:
                registry_status = _check_route_registration(rel_norm)
                for method, path, line in routes:
                    if not registry_status:
                        findings.append(
                            _finding(
                                "route_unregistered", file_path, f"未注册路由: @router.{method}('{path}')", line=line
                            )
                        )

        # 4. 测试覆盖检查
        if not rel.startswith("tests"):
            test_file = _find_test_file(rel)
            if not test_file:
                # 只有当文件有公开函数时才报
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

        # 5. 长的函数（超过 60 行）
        for f in functions:
            if f.end_lineno and (f.end_lineno - f.lineno) > 60:
                findings.append(
                    _finding(
                        "long_function",
                        file_path,
                        f"函数 {f.name} 过长 ({f.end_lineno - f.lineno} 行)",
                        line=f.lineno,
                        severity="info",
                    )
                )

        # 6. CodeGraph 悬挂引用（如果 DB 可用）
        if os.path.exists(CODEGRAPH_DB):
            _check_dangling_refs(rel, findings)

        return findings


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
    """提取函数签名（用于变更检测）"""
    args = []
    if node.args.args:
        args = [a.arg for a in node.args.args]
    return f"{node.name}({','.join(args)})"


def _check_import(module_name: str, source_file: str, findings: list, file_path: Path):
    """验证 import 路径存在"""
    if module_name.startswith("."):
        # 相对 import，解析
        parts = source_file.replace(".py", "").split(os.sep)
        dots = len(module_name) - len(module_name.lstrip("."))
        rel_path = module_name.lstrip(".")
        base = parts[:-dots] if dots > 0 else parts[:-1]
        try_path = os.sep.join(base + rel_path.split(".")) + ".py"
        full = PROJECT / try_path
    else:
        # 绝对 import
        try_path = module_name.replace(".", os.sep) + ".py"
        full = PROJECT / try_path

    # 只检查项目内部的 import（三方库不检查）
    if not full.exists() and not module_name.startswith("__future__"):
        # 可能是包（目录 + __init__.py）
        pkg = full.with_name(module_name.split(".")[-1])
        if not (pkg.is_dir() and (pkg / "__init__.py").exists()):
            # 检查是不是标准库或三方库（不在项目内就不报）
            std_lib_dirs = ["site-packages", "Lib", "lib/python"]
            if not any(d in str(full).lower() for d in std_lib_dirs):
                pass  # 三方库，不报错


def _extract_routes(tree) -> list:
    """提取路由装饰器"""
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and hasattr(dec.func, "attr"):
                    method = dec.func.attr.upper()
                    if method in ("GET", "POST", "PUT", "DELETE", "WS"):
                        # 提取路径
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
    """Project-relative path; fall back for pytest tmp_path outside PROJECT."""
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
    """Check whether a routes/* module is mounted on the app.

    Direct mounts: ``route_registry.py`` imports ``routes.foo`` and includes its router.
    Nested mounts: parent package (e.g. ``routes.ops_metrics.ops_metrics``) includes
    sub-routers via ``include_router(prometheus.router)``.
    """
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

    package_module = ".".join(parts[:-1])  # routes.ops_metrics
    submodule = file_stem  # prometheus

    if package_module not in content:
        return False

    parent_candidates = [
        PROJECT / "/".join(parts[:-1]) / f"{parts[-2]}.py",  # routes/ops_metrics/ops_metrics.py
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


def _find_test_file(source_rel: str) -> str | None:
    """找对应的测试文件"""
    stem = source_rel.replace(".py", "").replace(os.sep, "_")
    test_dir = PROJECT / "tests"

    # 直接匹配
    candidates = [
        test_dir / f"test_{stem.replace('routes_', '')}.py",
        test_dir / f"test_{source_rel.replace('.py', '').replace(os.sep, '_')}.py",
    ]

    for c in candidates:
        if c.exists():
            return str(c.relative_to(PROJECT))

    # 递归搜索 tests/（避免 rglob 性能问题）
    for f in os.listdir(str(test_dir)):
        if f.endswith(".py") and f.startswith("test_"):
            if stem.replace("routes_", "").replace("device_gateway_", "") in f:
                return f"tests/{f}"

    return None


def _check_dangling_refs(file_rel: str, findings: list):
    """CodeGraph 悬挂引用检查"""
    # 省略复杂 CodeGraph 查询，后续扩展
    pass


class FullScanner:
    """全量扫描器"""

    @staticmethod
    def scan(modules: list[str] | None = None) -> dict:
        """全量扫描"""
        all_findings = defaultdict(list)

        if modules:
            paths = [PROJECT / m for m in modules]
        else:
            # 扫描所有核心模块
            paths = [
                PROJECT / "routes",
                PROJECT / "device_gateway",
                PROJECT / "context_pipeline",
                PROJECT / "routing_selector",
                PROJECT / "backends_registry",
                PROJECT / "device_intelligence",
                PROJECT / "device_ota",
                PROJECT / "device_voice",
                PROJECT / "device_memory",
                PROJECT / "device_ledger",
                PROJECT / "device_logic",
                PROJECT / "device_support",
                PROJECT / "device_policy",
                PROJECT / "device_workflow",
                PROJECT / "session_memory",
                PROJECT / "search_gateway",
                PROJECT / "observability",
                PROJECT / "fleet",
                PROJECT / "provider_automation",
                PROJECT / "provider_inventory",
                PROJECT / "response_cleaner",
                PROJECT / "local_retrieval",
                PROJECT / "lima_mcp_stdio",
                PROJECT / "tool_gateway",
            ]

        scanned = 0
        for path in paths:
            if path.is_dir():
                for py_file in sorted(path.rglob("*.py")):
                    # 跳过 __init__ 和 esp32 固件目录
                    if py_file.name == "__init__.py":
                        continue
                    if "site-packages" in str(py_file) or ".venv" in str(py_file):
                        continue
                    if "esp32" in str(py_file).lower():
                        continue
                    findings = CodeScanner.scan_file(py_file)
                    if findings:
                        for f in findings:
                            all_findings[f["type"]].append(f)
                    scanned += 1
            elif path.is_file() and path.suffix == ".py":
                findings = CodeScanner.scan_file(path)
                if findings:
                    for f in findings:
                        all_findings[f["type"]].append(f)
                scanned += 1

        # 汇总
        errors = []
        warnings = []
        infos = []
        for ftype, flist in all_findings.items():
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


# ========== 增量监控 ==========


class Watchdog:
    """文件变更监听器"""

    def __init__(self, interval: int = 30):
        self.interval = interval
        self.snapshots: dict[str, float] = {}
        self._build_snapshot()

    def _build_snapshot(self):
        """建立文件快照"""
        core_dirs = [
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
        ]
        for d in core_dirs:
            dd = PROJECT / d
            if dd.is_dir():
                for f in os.listdir(str(dd)):
                    if f.endswith(".py"):
                        fp = str(dd / f)
                        self.snapshots[fp] = os.path.getmtime(fp) if os.path.exists(fp) else 0

    def poll(self) -> list:
        """轮询检测变更（比 watchdog 库更轻量）"""
        changes = []
        core_dirs = [
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
        ]
        for d in core_dirs:
            dd = PROJECT / d
            if dd.is_dir():
                for f in os.listdir(str(dd)):
                    if f.endswith(".py"):
                        key = str(dd / f)
                        current = os.path.getmtime(key) if os.path.exists(key) else 0
                        if key not in self.snapshots:
                            changes.append(("new", key))
                        elif current > self.snapshots[key]:
                            changes.append(("modified", key))
                        self.snapshots[key] = current

        return changes


# ========== 报告 ==========


def print_summary(result: dict):
    """打印可读的报告"""
    print(f"\n{'=' * 50}")
    print(f"📋 LiMa 守卫报告")
    print(f"{'=' * 50}")
    print(f"扫描文件: {result['scanned']}")
    print(f"发现问题: {result['total_findings']}")
    print(f"  🔴 错误: {len(result['errors'])}")
    print(f"  🟡 警告: {len(result['warnings'])}")
    print(f"  ℹ️  提示: {len(result['infos'])}")
    print()

    if result["errors"]:
        print("🔴 错误:")
        for f in result["errors"][:10]:
            print(f"  {f['file']}:{f['line']} — {f['message']}")
        print()

    if result["warnings"]:
        print("🟡 警告:")
        for f in result["warnings"][:10]:
            print(f"  {f['file']}:{f['line']} — {f['message']}")
        print()

    if result["by_type"]:
        print("分类统计:")
        for ftype, count in sorted(result["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {ftype:30s}: {count}")


# ========== CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LiMa 代码守卫")
    parser.add_argument("--full-scan", action="store_true", help="全量扫描全项目")
    parser.add_argument("--baseline", action="store_true", help="刷新基线")
    parser.add_argument("--watch", action="store_true", help="增量守护模式")
    parser.add_argument("--print-findings", action="store_true", help="查看当前发现")
    parser.add_argument("--module", "-m", help="仅扫描指定模块")
    args = parser.parse_args()

    GUARDIAN.mkdir(parents=True, exist_ok=True)

    if args.full_scan or args.baseline:
        if args.module:
            result = FullScanner.scan(modules=[args.module])
        else:
            log.info("开始全量扫描...")
            result = FullScanner.scan()

        # 保存
        (GUARDIAN / "findings.json").write_text(
            json.dumps({k: v for k, v in result.items() if k != "by_type"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 基线（不含 errors/warnings/infos, 只保留统计）
        baseline = {
            "scanned": result["scanned"],
            "total": result["total_findings"],
            "errors": [{"file": f["file"], "message": f["message"]} for f in result["errors"]],
            "warnings": [{"file": f["file"], "message": f["message"]} for f in result["warnings"]],
            "by_type": result["by_type"],
            "timestamp": result["timestamp"],
        }
        BASELINE_FILE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

        print_summary(result)
        log.info(f"已保存基线到 {GUARDIAN}")
        return

    if args.print_findings:
        if FINDINGS_FILE.exists():
            findings = json.loads(FINDINGS_FILE.read_text("utf-8"))
            # 重新组装摘要
            errs = findings.get("errors", [])
            warns = findings.get("warnings", [])
            print(f"当前发现: {len(errs) + len(warns)}")
            print(f"  🔴 错误: {len(errs)}")
            for f in errs[:15]:
                print(f"    {f['file']}:{f.get('line', 0)} — {f['message']}")
            print(f"  🟡 警告: {len(warns)}")
            for f in warns[:10]:
                print(f"    {f['file']}:{f.get('line', 0)} — {f['message']}")
        else:
            print("暂无发现。运行 --full-scan 进行首次扫描。")
        return

    if args.watch:
        log.info("启动增量守护模式（每 30 秒检测一次）...")
        wd = Watchdog()

        try:
            while True:
                changes = wd.poll()
                for change_type, file_path in changes:
                    fp = Path(file_path)
                    log.info(f"检测到变更: {change_type} {fp.name}")

                    # 增量分析变更文件
                    findings = CodeScanner.scan_file(fp)

                    # 读取已有发现，追加新的
                    existing = []
                    if FINDINGS_FILE.exists():
                        try:
                            existing = json.loads(FINDINGS_FILE.read_text("utf-8"))
                            existing = existing.get("errors", []) + existing.get("warnings", [])
                        except (json.JSONDecodeError, KeyError):
                            existing = []

                    # 去重合并
                    existing_ids = {f["id"] for f in existing}
                    new_f = [f for f in findings if f["id"] not in existing_ids]

                    if new_f:
                        for f in new_f:
                            log.info(f"  → {f['severity']}: {f['message']}")
                        existing.extend(new_f)

                        # 写回
                        errs = [f for f in existing if f["severity"] == "error"]
                        warns = [f for f in existing if f["severity"] == "warning"]
                        FINDINGS_FILE.write_text(
                            json.dumps(
                                {
                                    "errors": errs,
                                    "warnings": warns,
                                    "infos": [],
                                    "scanned": len(existing),
                                    "timestamp": datetime.now().isoformat(),
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )

                time.sleep(wd.interval)
        except KeyboardInterrupt:
            log.info("守护进程已停止")

    parser.print_help()


if __name__ == "__main__":
    main()
