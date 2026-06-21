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
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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


# ========== 工具实现 ==========


def tool_server_status(host: str | None = None) -> str:
    """查看服务器 LiMa 进程状态"""
    servers = get_servers()

    results = []
    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # 系统概览
        uptime = run_ssh(shost, "uptime")
        if uptime:
            results.append(f"  Uptime: {uptime}")

        # LiMa 进程
        lima_procs = run_ssh(shost, "ps aux | grep -E 'python|uvicorn|gunicorn' | grep -v grep || echo '无'")
        if lima_procs:
            lines = lima_procs.split("\n")
            for l in lines[:10]:
                l = re.sub(r"\s+", " ", l.strip())
                if l and l != "无":
                    results.append(f"  {l}")

        # 内存/CPU
        mem = run_ssh(shost, "free -h | head -2")
        if mem:
            results.append(f"  {mem}")

        # LiMa 版本
        ver = run_ssh(shost, "cat /opt/lima/VERSION 2>/dev/null || cat /root/lima/VERSION 2>/dev/null || echo 'N/A'")
        if ver:
            results.append(f"  Version: {ver}")

        # Docker
        docker = run_ssh(shost, "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'no docker'")
        if docker:
            for d in docker.split("\n"):
                results.append(f"  Docker: {d}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_device_connections(host: str | None = None) -> str:
    """查看实时设备连接"""
    servers = get_servers()
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # WebSocket 连接数
        ws = run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")
        if ws:
            results.append(f"  WebSocket 连接: {ws.strip()}")

        # Redis 连接数
        redis = run_ssh(shost, "ss -tnp | grep 6379 | grep ESTAB | wc -l")
        if redis:
            results.append(f"  Redis 连接: {redis.strip()}")

        # 最近设备会话
        sessions = run_ssh(
            shost,
            "grep -c 'session_start' /var/log/lima/access.log 2>/dev/null || grep -c 'session' /var/log/lima/app.log 2>/dev/null || echo 'N/A'",
        )
        if sessions and sessions != "N/A":
            results.append(f"  今日会话: {sessions.strip()}")

        # 系统文件描述符
        fds = run_ssh(shost, "lsof -i :8080 2>/dev/null | wc -l || echo 'N/A'")
        if fds and fds != "N/A":
            results.append(f"  端口 8080 文件描述符: {fds.strip()}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_tail_log(module: str, lines: int = 30, host: str | None = None) -> str:
    """按模块查看实时日志"""
    servers = get_servers()
    results = []

    # 日志路径猜测
    log_paths = [
        f"/var/log/lima/{module}.log",
        f"/var/log/lima/app.log",
        f"/opt/lima/logs/{module}.log",
        f"/root/lima/logs/latest.log",
    ]

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # 找到最近的日志文件
        found = False
        for lp in log_paths:
            exists = run_ssh(shost, f"test -f {lp} && echo 'yes' || echo 'no'")
            if exists and "yes" in exists:
                log_content = run_ssh(shost, f"tail -{lines} {lp}")
                if log_content:
                    results.append(f"  {lp}:")
                    results.append(log_content)
                    found = True
                    break

        if not found:
            # journald 回退
            journal = run_ssh(shost, f"journalctl -u lima* --no-pager -n {lines} 2>/dev/null || echo 'no journal'")
            if journal and "no journal" not in journal:
                results.append(f"  journald:")
                results.append(journal)
            else:
                results.append(f"  (未找到日志文件)")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_health_check(host: str | None = None) -> str:
    """关键端点健康检查"""
    servers = get_servers()
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # HTTP 健康端点
        health = run_ssh(
            shost,
            "curl -s -o /dev/null -w '%{http_code} %{time_total}s' http://localhost:8080/health 2>/dev/null || echo 'N/A'",
        )
        if health and health != "N/A":
            code, t = health.split()
            status = "✅" if code in ("200", "204") else "❌"
            results.append(f"  {status} /health: {code} ({t}s)")

        # 模型列表
        models = run_ssh(
            shost, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/v1/models 2>/dev/null || echo 'N/A'"
        )
        if models and models != "N/A":
            status = "✅" if models in ("200", "204") else "❌"
            results.append(f"  {status} /v1/models: {models}")

        # 设备连接端点
        device = run_ssh(
            shost,
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/device/v1/status 2>/dev/null || echo 'N/A'",
        )
        if device and device != "N/A":
            status = "✅" if device == "200" else "⚠️"
            results.append(f"  {status} /device/v1/status: {device}")

        # SSL
        ssl = run_ssh(
            shost, "curl -sk -o /dev/null -w '%{http_code}' https://localhost:443/health 2>/dev/null || echo 'N/A'"
        )
        if ssl and ssl != "N/A":
            status = "✅" if ssl == "200" else "⚠️"
            results.append(f"  {status} SSL: {ssl}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_restart_service(service: str = "lima", host: str | None = None) -> str:
    """安全重启 LiMa 服务（带健康检查）"""
    servers = get_servers()
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # 检查当前状态
        current = run_ssh(
            shost,
            f"systemctl is-active {service} 2>/dev/null || supervisorctl status {service} 2>/dev/null || echo 'unknown'",
        )
        results.append(f"  当前状态: {current}")

        # 重启
        results.append(f"  🔄 重启 {service}...")
        run_ssh(
            shost,
            f"systemctl restart {service} 2>/dev/null || supervisorctl restart {service} 2>/dev/null || docker restart {service} 2>/dev/null || echo 'restart attempted'",
        )

        # 等待启动
        time.sleep(3)

        # 健康检查
        healthy = False
        for _ in range(5):
            check = run_ssh(
                shost, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || echo 'N/A'"
            )
            if check and check in ("200", "204"):
                healthy = True
                break
            time.sleep(2)

        if healthy:
            results.append(f"  ✅ {service} 重启成功")
        else:
            results.append(f"  ⚠️ 健康检查失败，请手动确认")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


# ========== MCP 协议 ==========

TOOLS = {
    "server_status": {
        "description": "查看服务器 LiMa 进程状态。查询阿里云/京东云服务器上 LiMa 的运行状态、版本、内存等信息。host 可选过滤。",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string", "description": "可选: 服务器主机名或标签（aliyun/jdcloud）"}},
        },
    },
    "device_connections": {
        "description": "查看实时设备连接数。包括 WebSocket 连接、Redis 会话、今日会话量。",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string", "description": "可选: 服务器过滤"}},
        },
    },
    "tail_log": {
        "description": "按模块查看实时日志。从生产服务器获取 LiMa 指定模块的 N 行日志。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "模块名: app/gateway/ota/proxy 等"},
                "lines": {"type": "integer", "description": "行数", "default": 30},
                "host": {"type": "string", "description": "可选: 服务器过滤"},
            },
            "required": ["module"],
        },
    },
    "health_check": {
        "description": "关键端点健康检查。测试 /health, /v1/models, /device/v1/status, SSL 端点的 HTTP 状态码。",
        "inputSchema": {
            "type": "object",
            "properties": {"host": {"type": "string", "description": "可选: 服务器过滤"}},
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
                "serverInfo": {"name": "lima-ops", "version": "1.0.0"},
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
            if tool == "server_status":
                text = tool_server_status(args.get("host"))
            elif tool == "device_connections":
                text = tool_device_connections(args.get("host"))
            elif tool == "tail_log":
                text = tool_tail_log(args["module"], args.get("lines", 30), args.get("host"))
            elif tool == "health_check":
                text = tool_health_check(args.get("host"))
            elif tool == "restart_service":
                text = tool_restart_service(args.get("service", "lima"), args.get("host"))
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
