#!/usr/bin/env python3
"""
LimGuard 守卫适配器 MCP —— 读取 findings.json 并提供给 AI。
Cursor/Kimi 直接调 MCP 工具获取项目当前发现，
不需要人工转发。

工具:
- get_findings: 获取所有发现，可按文件/严重级别过滤
- get_file_findings: 获取指定文件的发现（AI 编辑文件前调用）
- auto_fix_suggestion: 对指定发现生成修复建议
"""

import json
import os
import sys
from pathlib import Path

FINDINGS_FILE = Path("D:/QWEN3.0/.guardian/findings.json")
BASELINE_FILE = Path("D:/QWEN3.0/.guardian/baseline.json")


def load_findings() -> dict:
    if FINDINGS_FILE.exists():
        try:
            return json.loads(FINDINGS_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, KeyError):
            return {"errors": [], "warnings": [], "infos": []}
    return {"errors": [], "warnings": [], "infos": []}


def get_file_findings(file_path: str) -> list:
    """获取特定文件的所有发现"""
    findings = load_findings()
    all_items = findings.get("errors", []) + findings.get("warnings", []) + findings.get("infos", [])
    return [f for f in all_items if f.get("file", "").replace("\\", "/") == file_path.replace("\\", "/")]


def get_findings(severity: str = None, limit: int = 20) -> dict:
    """获取所有发现，可按严重级别过滤"""
    findings = load_findings()

    if severity:
        return {severity: findings.get(severity, [])[:limit]}

    return {
        "errors": findings.get("errors", [])[:limit],
        "warnings": findings.get("warnings", [])[:limit],
        "infos": findings.get("infos", [])[:limit],
    }


def auto_fix_suggestion(finding: dict) -> str:
    """对指定发现生成修复建议"""
    ftype = finding.get("type", "")
    file_path = finding.get("file", "").replace("\\", "/")

    if ftype == "route_unregistered":
        parts = file_path.split("/")
        module = file_path.replace(".py", "").replace("/", ".")
        if len(parts) >= 3 and parts[0] == "routes":
            parent = "/".join(parts[:-1])
            submodule = Path(file_path).stem
            return (
                f"嵌套路由 `{file_path}` 应在父模块 `{parent}/` 中挂载:\n"
                f"```python\n"
                f"from routes.{parts[1]} import {submodule}\n"
                f"router.include_router({submodule}.router)\n"
                f"```\n"
                f"若为新顶层包，则在 `routes/route_registry.py` 的 `_try_include` 列表注册 `{module}`。\n"
                f"运行 `python scripts/lima_guardian.py --full-scan` 确认已修复。"
            )
        return (
            f"在 `routes/route_registry.py` 中注册 `{module}`（`_try_include` 或 `include_router`）。\n"
            f"运行 `python scripts/lima_guardian.py --full-scan` 确认已修复。"
        )

    suggestions = {
        "no_test_file": (
            f"为 `{file_path}` 补充测试:\n"
            f"- 路由模块可扩展现有 `tests/test_routes_auth_contract.py` 契约 smoke\n"
            f"- 或创建 `tests/test_{file_path.replace('.py', '').replace('/', '_').replace('routes_', '')}.py`\n"
            f"- 运行 `python scripts/analyze_test_coverage.py -m {file_path.split('/')[0]}` 查看 import 级覆盖"
        ),
        "parse_error": "检查文件语法错误。运行 `python -m py_compile <file>` 查看具体错误。",
        "long_function": "考虑将函数拆分为多个小函数（单一职责原则）。",
    }

    return suggestions.get(ftype, f"检查 `{file_path}` 的 {ftype} 问题并修复。")


TOOLS = {
    "get_findings": {
        "description": "获取 LiMa 项目当前所有代码发现。支持按 severity 过滤 (errors/warnings/infos)。AI 应在代码编辑前调用此工具了解项目健康状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "过滤: errors / warnings / infos",
                    "enum": ["errors", "warnings", "infos"],
                },
                "limit": {"type": "integer", "description": "返回条数上限", "default": 20},
            },
        },
    },
    "get_file_findings": {
        "description": "获取指定文件的所有发现。AI 在编辑文件前应调用此工具，检查文件是否有已知问题需要一并修复。",
        "inputSchema": {
            "type": "object",
            "properties": {"file_path": {"type": "string", "description": "相对路径，如 routes/admin_api.py"}},
            "required": ["file_path"],
        },
    },
    "auto_fix": {
        "description": "对指定发现自动生成修复建议。AI 可根据建议直接修改代码。",
        "inputSchema": {
            "type": "object",
            "properties": {"finding_id": {"type": "string", "description": "发现的 id"}},
            "required": ["finding_id"],
        },
    },
}


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "limaguard", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": k, "description": v["description"], "inputSchema": v["inputSchema"]}
                    for k, v in TOOLS.items()
                ]
            },
        }

    if method == "tools/call":
        tool = req["params"]["name"]
        args = req["params"].get("arguments", {})

        try:
            if tool == "get_findings":
                text = json.dumps(
                    get_findings(args.get("severity"), args.get("limit", 20)), ensure_ascii=False, indent=2
                )
            elif tool == "get_file_findings":
                text = json.dumps(get_file_findings(args["file_path"]), ensure_ascii=False, indent=2)
            elif tool == "auto_fix":
                findings = load_findings()
                all_items = findings.get("errors", []) + findings.get("warnings", []) + findings.get("infos", [])
                target = next((f for f in all_items if f.get("id") == args["finding_id"]), None)
                if target:
                    text = auto_fix_suggestion(target)
                else:
                    text = f"未找到发现: {args['finding_id']}"
            else:
                raise ValueError(f"Unknown tool: {tool}")

            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req_id, "result": {}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp and "id" in resp and resp["id"] is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    main()
