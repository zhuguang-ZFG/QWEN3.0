#!/usr/bin/env python3
"""
LiMa Code Query MCP Server — 实时代码检索工具

包装 code_context/ 的语义检索 + graph_index 的关系查询，
让 Cursor/Kimi 可以直接通过 MCP 工具查询 LiMa 代码库。

工具：
- search_code: 语义搜索代码（按相关度返回文件）
- get_module_context: 获取模块结构（symbols + imports）
- find_related: 找关联文件（基于导入关系）
- trace_symbol: 追踪符号定义和引用
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

logger = logging.getLogger(__name__)

from lima_mcp_stdio.lima_code_query_core import LimaCodeQuery

# ===== MCP 协议实现 =====

_TOOLS_SCHEMA = [
    {
        "name": "search_code",
        "description": "语义搜索 LiMa 代码库，返回相关文件和符号",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词（支持模块名、函数名、概念）"},
                "limit": {"type": "integer", "description": "返回结果数（默认8）"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_module_context",
        "description": "获取模块结构信息：类、函数、导入关系",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对项目根目录的 Python 文件路径，如 routes/chat_handler.py",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "find_related",
        "description": "找关联文件：基于导入关系和目录相邻",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "max_results": {"type": "integer", "description": "最大返回数"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "trace_symbol",
        "description": "跨文件追踪符号定义和引用",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {"type": "string", "description": "符号名（函数/类/变量名）"},
                "max_results": {"type": "integer"},
            },
            "required": ["symbol_name"],
        },
    },
]


code_query = LimaCodeQuery()


def _handle_tool_call(tool_name: str, tool_args: dict) -> dict:
    """Dispatch a single MCP tool call and wrap the result for JSON-RPC."""
    if tool_name == "search_code":
        result = code_query.search_code(tool_args.get("query", ""), tool_args.get("limit", 8))
    elif tool_name == "get_module_context":
        result = code_query.get_module_context(tool_args.get("path", ""))
    elif tool_name == "find_related":
        result = code_query.find_related(tool_args.get("path", ""), tool_args.get("max_results", 10))
    elif tool_name == "trace_symbol":
        result = code_query.trace_symbol(tool_args.get("symbol_name", ""), tool_args.get("max_results", 15))
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return {
        "jsonrpc": "2.0",
        "id": None,
        "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]},
    }


def handle_request(request: dict) -> dict:
    """处理 MCP JSON-RPC 请求"""
    req_id = request.get("id")
    method = request.get("method", "")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _TOOLS_SCHEMA}}

    if method == "tools/call":
        params = request.get("params", {})
        response = _handle_tool_call(params.get("name", ""), params.get("arguments", {}))
        response["id"] = req_id
        return response

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "lima-code-query", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    """STDIO MCP 服务器入口"""
    import sys

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError as e:
            logger.warning("invalid JSON-RPC input: %s", e)
        except Exception as e:
            error_response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
