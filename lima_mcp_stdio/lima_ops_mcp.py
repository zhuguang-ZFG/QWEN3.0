#!/usr/bin/env python3
"""
LiMa 生产运维 MCP 服务器。
通过 SSH MCP 代理，提供 LiMa 专用的生产调试命令。

工具:
- server_status: 查看服务器进程/内存/版本
- device_connections: 实时设备连接数/会话
- tail_log: 按模块查看日志
- health_check: 关键端点健康检查
- restart: 安全重启服务（带健康检查）

依赖: ssh-mcp-server 已配置
"""

import json
import os
import sys
from pathlib import Path

from lima_mcp_stdio.lima_ops_tools import (
    tool_device_connections,
    tool_health_check,
    tool_restart_service,
    tool_server_status,
    tool_tail_log,
)

SSH_CONFIG = Path(os.path.expanduser("~/.qclaw/workspace/ssh-config.json"))


def run_ssh(host: str, cmd: str, timeout: int = 10) -> str | None:
    """通过本地 ssh 命令执行"""
    import subprocess

    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", f"root@{host}", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return f"SSH error: {e}"


def get_servers() -> dict:
    """从 SSH 配置获取服务器列表"""
    try:
        config = json.loads(SSH_CONFIG.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"aliyun": {"host": "47.112.162.80", "label": "阿里云"}}

    servers = {}
    if isinstance(config, list):
        for s in config:
            servers[s.get("host")] = {"host": s.get("host"), "label": s.get("name", s.get("host"))}
    elif isinstance(config, dict):
        for name, s in config.items():
            if isinstance(s, dict) and "host" in s:
                servers[s["host"]] = {"host": s["host"], "label": name}
    return servers


# ========== MCP 协议 ==========

TOOLS = {
    "server_status": {
        "description": "查看服务器 LiMa 进程状态（摘要优先，省 70% token）。summary=True 只返回一行关键指标，False 返回完整 ps/free/docker。。查询阿里云/京东云服务器上 LiMa 的运行状态、版本、内存等信息。host 可选过滤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "可选: 服务器过滤（aliyun/jdcloud）"},
                "summary": {
                    "type": "boolean",
                    "description": "摘要模式：只返回一行关键指标（uptime/mem/cpu/proc/ws）。省 70% token。",
                    "default": True,
                },
            },
        },
    },
    "device_connections": {
        "description": "查看实时设备连接数（摘要优先，省 50% token）。summary=True 单行数字，False 详细含 fd。。包括 WebSocket 连接、Redis 会话、今日会话量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "可选: 服务器过滤"},
                "summary": {
                    "type": "boolean",
                    "description": "摘要模式：只返回 ws/redis/session 数字。省 50% token。",
                    "default": True,
                },
            },
        },
    },
    "tail_log": {
        "description": "按模块查看实时日志（摘要优先，省 80% token）。summary=True 只返回行数+错误数，False 返回完整日志。。从生产服务器获取 LiMa 指定模块的 N 行日志。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "模块名: app/gateway/ota/proxy 等"},
                "lines": {"type": "integer", "description": "行数", "default": 30},
                "host": {"type": "string", "description": "可选: 服务器过滤"},
                "summary": {
                    "type": "boolean",
                    "description": "摘要模式：只返回行数+错误数汇总。省 80% token。summary=False 展开详情。",
                    "default": True,
                },
            },
            "required": ["module"],
        },
    },
    "health_check": {
        "description": "关键端点健康检查（摘要优先，省 60% token）。summary=True 单行状态，False 详细含响应时间+SSL。。测试 /health, /v1/models, /device/v1/status, SSL 端点的 HTTP 状态码。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "可选: 服务器过滤"},
                "summary": {
                    "type": "boolean",
                    "description": "摘要模式：单行 ok/3 状态。省 60% token。",
                    "default": True,
                },
            },
        },
    },
    "restart_service": {
        "description": "安全重启 LiMa 服务（带健康检查自动确认）。重启前检查当前状态，重启后等待并验证健康。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "服务名", "default": "lima"},
                "host": {"type": "string", "description": "可选: 服务器过滤"},
            },
        },
    },
}


def _handle_initialize(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "lima-ops", "version": "1.0.0"},
        },
    }


def _handle_tools_list(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {"name": k, "description": v["description"], "inputSchema": v["inputSchema"]} for k, v in TOOLS.items()
            ]
        },
    }


def _dispatch_tool(tool: str, args: dict, servers: dict) -> str:
    if tool == "server_status":
        return tool_server_status(args.get("host"), args.get("summary", True), run_ssh=run_ssh, servers=servers)
    if tool == "device_connections":
        return tool_device_connections(args.get("host"), args.get("summary", True), run_ssh=run_ssh, servers=servers)
    if tool == "tail_log":
        return tool_tail_log(
            args["module"],
            args.get("lines", 30),
            args.get("host"),
            args.get("summary", True),
            run_ssh=run_ssh,
            servers=servers,
        )
    if tool == "health_check":
        return tool_health_check(args.get("host"), args.get("summary", True), run_ssh=run_ssh, servers=servers)
    if tool == "restart_service":
        return tool_restart_service(args.get("service", "lima"), args.get("host"), run_ssh=run_ssh, servers=servers)
    raise ValueError(f"Unknown tool: {tool}")


def _handle_tool_call(req: dict) -> dict:
    req_id = req.get("id")
    tool = req["params"]["name"]
    args = req["params"].get("arguments", {})
    try:
        text = _dispatch_tool(tool, args, get_servers())
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return _handle_initialize(req_id)
    if method == "tools/list":
        return _handle_tools_list(req_id)
    if method == "tools/call":
        return _handle_tool_call(req)

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
