#!/usr/bin/env python3
"""MCP protocol layer for prompt compression — JSON-RPC dispatch."""
from __future__ import annotations

import json
import sys

TOOLS = {
    "compress_text": {
        "description": "压缩长文本/日志。保留首尾关键行 + 中间抽取含 error/warning 的关键句。短文本不处理。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要压缩的文本"},
                "target_ratio": {
                    "type": "number",
                    "description": "目标压缩比 (0.1-0.5)",
                    "default": 0.3,
                },
            },
            "required": ["text"],
        },
    },
    "compress_code": {
        "description": "压缩代码：去除注释/文档字符串/多余空行，保留 TODO/FIXME 等重要注释。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要压缩的代码"},
            },
            "required": ["code"],
        },
    },
    "compress_json": {
        "description": "压缩 JSON/结构化数据：去 null/默认值，数组只保留首尾各 N 项，深度>5 截断。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_str": {"type": "string", "description": "JSON 字符串"},
                "max_items": {
                    "type": "integer",
                    "description": "数组保留最大项数",
                    "default": 8,
                },
            },
            "required": ["json_str"],
        },
    },
    "compress_context": {
        "description": "智能压缩：自动检测文本/代码/JSON/日志类型，选最优策略。通用入口。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "任意长文本"},
            },
            "required": ["text"],
        },
    },
}


def _handle_tool_call(req_id, params, compress_text, compress_code, compress_json, compress_context):
    """Dispatch a tools/call request to the appropriate compressor."""
    tool = params["name"]
    args = params.get("arguments", {})
    try:
        if tool == "compress_text":
            text = compress_text(args["text"], args.get("target_ratio", 0.3))
        elif tool == "compress_code":
            text = compress_code(args["code"])
        elif tool == "compress_json":
            text = compress_json(args["json_str"], args.get("max_items", 8))
        elif tool == "compress_context":
            text = compress_context(args["text"])
        else:
            raise ValueError(f"Unknown tool: {tool}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32603, "message": str(e)},
        }


def handle_request(req: dict) -> dict:
    # Lazy imports — compression module loads us first, so we import it at call time
    from lima_mcp_stdio.prompt_compress_mcp import (
        compress_text,
        compress_code,
        compress_json,
        compress_context,
    )

    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "prompt-compress", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": k,
                        "description": v["description"],
                        "inputSchema": v["inputSchema"],
                    }
                    for k, v in TOOLS.items()
                ]
            },
        }

    if method == "tools/call":
        return _handle_tool_call(req_id, req["params"], compress_text, compress_code, compress_json, compress_context)

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
