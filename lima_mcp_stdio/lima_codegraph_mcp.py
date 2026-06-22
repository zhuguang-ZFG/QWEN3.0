#!/usr/bin/env python3
"""
LiMa CodeGraph Impact Analysis MCP 服务器。
直接从 CodeGraph 93MB SQLite 数据库查询:
- 影响分析：改 X 会影响到哪些模块？
- 依赖分析：X 依赖哪些模块？
- 符号追踪：Y 在哪里定义/使用？
- FTS5 搜索：语义搜索代码符号

STDIO MCP 协议。

用法: python scripts/lima_codegraph_mcp.py
配置到 mcp.json:
{
  "lima-codegraph": {
    "command": "python",
    "args": ["scripts/lima_codegraph_mcp.py"],
    "cwd": "D:/QWEN3.0"
  }
}
"""

import json
import sys

from lima_codegraph_tools import (
    TOOLS,
    tool_dependency_analysis,
    tool_impact_analysis,
    tool_module_structure,
    tool_search_symbols,
)


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
                "serverInfo": {"name": "lima-codegraph", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": k, "description": v["description"], "inputSchema": v["parameters"]}
                    for k, v in TOOLS.items()
                ]
            },
        }

    if method == "tools/call":
        tool_name = req["params"]["name"]
        arguments = req["params"].get("arguments", {})

        try:
            if tool_name == "impact_analysis":
                result_raw = tool_impact_analysis(arguments["symbol_name"], arguments.get("depth", 1))
            elif tool_name == "dependency_analysis":
                result_raw = tool_dependency_analysis(arguments["symbol_name"])
            elif tool_name == "search_symbols":
                result_raw = tool_search_symbols(arguments["query"], arguments.get("limit", 15))
            elif tool_name == "module_structure":
                result_raw = tool_module_structure(arguments["module_path"])
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result_raw}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    # 通知忽略
    return {"jsonrpc": "2.0", "id": req_id, "result": {}}


def main():
    """STDIO MCP 主循环"""
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
