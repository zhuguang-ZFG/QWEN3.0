"""Minimal JSON-RPC MCP server for P0 device drawing/writing integration."""

from __future__ import annotations

import json
import logging
import os
import sys

import httpx

DLC_API_URL = os.environ.get("DLC_API_URL", "http://127.0.0.1:8081")
# dlc_api /dlc/tasks/dispatch and /dlc/devices/{id}/status require
# verify_dlc_api_token (Authorization: Bearer <token>). Configure DLC_API_TOKEN
# on the VPS .env with the device's token; without it those endpoints return 401.
DLC_API_TOKEN = os.environ.get("DLC_API_TOKEN", "")

logger = logging.getLogger(__name__)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {DLC_API_TOKEN}"} if DLC_API_TOKEN else {}


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
    "dlc.draw_from_image": {
        "description": "将指定图片 URL 矢量化并在绘图机上绘制。需要 device_id 和 image_url。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "image_url": {"type": "string", "description": "图片 URL（http/https）"},
            },
            "required": ["device_id", "image_url"],
        },
    },
    "dlc.get_device_status": {
        "description": "查询绘图机当前状态（在线/工作/任务/影子）。需要 device_id。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
            },
            "required": ["device_id"],
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


def _submit(client: httpx.Client, endpoint: str, payload: dict, idem_key: str | None = None) -> dict:
    url = f"{DLC_API_URL}{endpoint}"
    headers = _auth_headers()
    if idem_key is not None:
        headers["Idempotency-Key"] = f"mcp-{idem_key}"
    try:
        resp = client.post(url, json=payload, headers=headers)
    except Exception as exc:
        logger.warning("dlc_api request failed: %s", exc)
        return {"status": "failed", "error": "dlc_api unreachable"}
    try:
        return resp.json()
    except Exception as exc:
        logger.warning("dlc_api invalid response: %s", exc)
        return {"status": "failed", "error": "invalid response from dlc_api"}


def _get_json(client: httpx.Client, endpoint: str) -> dict:
    """GET JSON from dlc_api; returns {"error": ...} on failure."""
    url = f"{DLC_API_URL}{endpoint}"
    try:
        resp = client.get(url, headers=_auth_headers())
    except Exception as exc:
        logger.warning("dlc_api GET failed: %s", exc)
        return {"error": "dlc_api unreachable"}
    try:
        return resp.json()
    except Exception as exc:
        logger.warning("dlc_api invalid response: %s", exc)
        return {"error": "invalid response from dlc_api"}


def _format_submission(client: httpx.Client, req_id: object, endpoint: str, payload: dict) -> dict:
    result = _submit(client, endpoint, payload, idem_key=str(req_id))
    if result.get("error"):
        return _tool_error(req_id, -32603, result["error"])
    summary = (
        f"任务已提交: status={result.get('status')}, sent={result.get('sent')}, "
        f"queue_depth={result.get('queue_depth')}, task_id={result.get('task_id') or 'n/a'}"
    )
    return _tool_result(req_id, summary)


def _handle_write_text(client: httpx.Client, req_id: object, args: dict) -> dict:
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


def _handle_draw_generated(client: httpx.Client, req_id: object, args: dict) -> dict:
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


def _handle_draw_from_image(client: httpx.Client, req_id: object, args: dict) -> dict:
    device_id = str(args.get("device_id", "")).strip()
    image_url = str(args.get("image_url", "")).strip()
    if not device_id or not image_url:
        return _tool_error(req_id, -32602, "device_id and image_url are required")
    return _format_submission(
        client,
        req_id,
        "/dlc/tasks/dispatch",
        {"type": "draw_from_image", "device_id": device_id, "payload": {"image_url": image_url}},
    )


def _handle_get_device_status(client: httpx.Client, req_id: object, args: dict) -> dict:
    device_id = str(args.get("device_id", "")).strip()
    if not device_id:
        return _tool_error(req_id, -32602, "device_id is required")
    result = _get_json(client, f"/dlc/devices/{device_id}/status")
    if result.get("error"):
        return _tool_error(req_id, -32603, result["error"])
    summary = (
        f"设备状态: online={result.get('online')}, working={result.get('working')}, "
        f"task={result.get('active_task_id') or '无'}, fw={result.get('firmware_version') or '未知'}"
    )
    return _tool_result(req_id, summary)


TOOL_HANDLERS = {
    "dlc.write_text": _handle_write_text,
    "dlc.draw_generated": _handle_draw_generated,
    "dlc.draw_from_image": _handle_draw_from_image,
    "dlc.get_device_status": _handle_get_device_status,
}


def _handle_tools_call(client: httpx.Client, req_id: object, params: object) -> dict:
    """Dispatch a tools/call request to the appropriate DLC tool.

    P1 #5（review 复查）：params/arguments 可能是合法 JSON 但非对象（list/str/int），
    必须显式校验类型并返回 -32602 Invalid params，不能让 .get 抛 AttributeError。
    """
    if not isinstance(params, dict):
        return _tool_error(req_id, -32602, "params must be an object")
    name = params.get("name")
    if not isinstance(name, str):
        return _tool_error(req_id, -32602, "name must be a string")
    args = params.get("arguments", {})
    if not isinstance(args, dict):
        return _tool_error(req_id, -32602, "arguments must be an object")
    handler = TOOL_HANDLERS.get(name)
    if handler:
        return handler(client, req_id, args)
    return _tool_error(req_id, -32601, "unknown tool")


def handle_request(client: httpx.Client, req: dict) -> dict:
    """Route a JSON-RPC request to the correct handler."""
    # P1 #5（隐藏问题审查）：合法 JSON 但非对象（list/str/int）必须返回 -32600，
    # 不能让 req.get 抛 AttributeError 崩溃调用方。
    if not isinstance(req, dict):
        return _tool_error(None, -32600, "Invalid Request: expected JSON object")
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "dlc-mcp-p0", "version": "0.4.0-p3"},
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

    # MCP keepalive: XiaoZhi periodically sends ping; spec requires an empty result.
    # Without this the broker treats the connection as unhealthy and closes it (~24s).
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    # Notifications (no id, e.g. notifications/initialized) require no response.
    if method and method.startswith("notifications/"):
        return {}

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
            # P1 #5：handle_request 必须纳入 try，任何畸形请求/内部异常
            # 都返回错误响应，不能让主循环退出（否则 mcp_pipe 频繁重连）。
            try:
                resp = handle_request(client, req)
            except Exception as exc:  # noqa: BLE001 - 不能让主循环崩
                logger.warning("MCP handle_request internal error: %s", exc)
                resp = _tool_error(None, -32603, "Internal error")
            if resp and resp.get("id") is not None:
                payload = json.dumps(resp, ensure_ascii=False) + "\n"
                sys.stdout.buffer.write(payload.encode("utf-8"))
                sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
