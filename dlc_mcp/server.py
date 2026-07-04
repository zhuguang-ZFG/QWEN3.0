"""Minimal JSON-RPC MCP server for P0 device drawing/writing integration."""

from __future__ import annotations

import json
import logging
import os
import sys

import httpx

DLC_API_URL = os.environ.get("DLC_API_URL", "http://127.0.0.1:18080")

logger = logging.getLogger(__name__)

TOOLS = {
    "dlc.write_text": {
        "description": "在绘图机上书写指定文本。需要 device_id 和 text。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "text": {"type": "string", "description": "要书写的文本"},
            },
            "required": ["device_id", "text"],
        },
    },
    "dlc.draw_generated": {
        "description": "根据提示词 AI 生成图像并在绘图机上绘制。需要 device_id 和 prompt。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "prompt": {"type": "string", "description": "绘画提示词"},
            },
            "required": ["device_id", "prompt"],
        },
    },
}


def _tool_result(req_id: object, text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": text}]},
    }


def _tool_error(req_id: object, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _submit(client: httpx.Client, endpoint: str, payload: dict) -> dict:
    url = f"{DLC_API_URL}{endpoint}"
    try:
        resp = client.post(url, json=payload)
    except Exception as exc:
        logger.warning("dlc_api request failed: %s", exc)
        return {"status": "failed", "error": f"dlc_api unreachable: {exc}"}
    try:
        return resp.json()
    except Exception as exc:
        logger.warning("dlc_api invalid response: %s", exc)
        return {"status": "failed", "error": f"invalid response: {exc}"}


def _format_submission(client: httpx.Client, req_id: object, endpoint: str, payload: dict) -> dict:
    result = _submit(client, endpoint, payload)
    if result.get("error"):
        return _tool_error(req_id, -32603, result["error"])
    summary = (
        f"任务已提交: status={result.get('status')}, sent={result.get('sent')}, "
        f"queue_depth={result.get('queue_depth')}, task_id={result.get('task_id') or 'n/a'}"
    )
    return _tool_result(req_id, summary)


def _handle_tools_call(client: httpx.Client, req_id: object, params: dict) -> dict:
    """Dispatch a tools/call request to the appropriate DLC tool."""
    name = params.get("name")
    args = params.get("arguments", {})

    if name == "dlc.write_text":
        device_id = str(args.get("device_id", "")).strip()
        text = str(args.get("text", "")).strip()
        if not device_id or not text:
            return _tool_error(req_id, -32602, "device_id and text are required")
        return _format_submission(
            client,
            req_id,
            "/dlc/tasks/dispatch",
            {"type": "write_text", "device_id": device_id, "payload": {"text": text}},
        )

    if name == "dlc.draw_generated":
        device_id = str(args.get("device_id", "")).strip()
        prompt = str(args.get("prompt", "")).strip()
        if not device_id or not prompt:
            return _tool_error(req_id, -32602, "device_id and prompt are required")
        return _format_submission(
            client,
            req_id,
            "/dlc/tasks/dispatch",
            {"type": "draw_generated", "device_id": device_id, "payload": {"prompt": prompt}},
        )

    return _tool_error(req_id, -32601, "unknown tool")


def handle_request(client: httpx.Client, req: dict) -> dict:
    """Route a JSON-RPC request to the correct handler."""
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "dlc-mcp-p0", "version": "0.1.0-p0"},
            },
        }

    if method == "tools/list":
        tools = [
            {"name": name, "description": meta["description"], "inputSchema": meta["inputSchema"]}
            for name, meta in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        return _handle_tools_call(client, req_id, req.get("params", {}))

    return _tool_error(req_id, -32601, "Method not found")


def main() -> None:
    with httpx.Client(timeout=60.0) as client:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = handle_request(client, req)
            if resp and resp.get("id") is not None:
                payload = json.dumps(resp, ensure_ascii=False) + "\n"
                sys.stdout.buffer.write(payload.encode("utf-8"))
                sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
