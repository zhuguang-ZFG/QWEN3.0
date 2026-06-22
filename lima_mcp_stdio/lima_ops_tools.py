#!/usr/bin/env python3
"""LiMa 运维工具函数 —— 从 lima_ops_mcp.py 提取。

每个工具函数接受 run_ssh、servers、logger 作为参数注入，
而非直接从父模块导入。
"""

import logging
import re
import time
from typing import Optional


def tool_server_status(
    host: str | None = None,
    summary: bool = True,
    run_ssh=None,
    servers: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """查看服务器 LiMa 进程状态"""
    if logger is None:
        logger = logging.getLogger(__name__)
    if servers is None:
        servers = {}

    results = []
    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]

        if summary:
            uptime = run_ssh(shost, "uptime | sed 's/.*up//;s/,.*//'")
            mem = run_ssh(shost, 'free -h | awk \'NR==2{print "mem:"$3"/"$2}\'')
            cpu = run_ssh(shost, "top -bn1 | grep 'Cpu(s)' | awk '{print \"cpu:\"$2\"%\"}'")
            proc_count = run_ssh(shost, "ps aux | grep -E 'python|uvicorn|gunicorn' | grep -v grep | wc -l")
            ver = run_ssh(shost, "cat /opt/lima/VERSION 2>/dev/null || echo 'N/A'")
            docker_count = run_ssh(shost, "docker ps -q 2>/dev/null | wc -l")
            ws_count = run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")
            results.append(
                f"[{label}] uptime:{uptime or '?'} | mem:{mem or '?'} | cpu:{cpu or '?'} | "
                f"proc:{(proc_count or '').strip() or '0'} | ver:{ver or 'N/A'} | "
                f"docker:{(docker_count or '').strip() or '0'} | ws:{(ws_count or '').strip() or '0'}"
            )
        else:
            results.append(f"\n=== {label} ({shost}) ===")
            uptime = run_ssh(shost, "uptime")
            if uptime:
                results.append(f"  Uptime: {uptime}")
            lima_procs = run_ssh(shost, "ps aux | grep -E 'python|uvicorn|gunicorn' | grep -v grep || echo '无'")
            if lima_procs:
                lines = lima_procs.split("\n")
                for l in lines[:10]:
                    l = re.sub(r"\s+", " ", l.strip())
                    if l and l != "无":
                        results.append(f"  {l}")
            mem = run_ssh(shost, "free -h | head -2")
            if mem:
                results.append(f"  {mem}")
            ver = run_ssh(
                shost,
                "cat /opt/lima/VERSION 2>/dev/null || cat /root/lima/VERSION 2>/dev/null || echo 'N/A'",
            )
            if ver:
                results.append(f"  Version: {ver}")
            docker = run_ssh(
                shost, "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'no docker'"
            )
            if docker:
                for d in docker.split("\n"):
                    results.append(f"  Docker: {d}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_device_connections(
    host: str | None = None,
    summary: bool = True,
    run_ssh=None,
    servers: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """查看实时设备连接"""
    if logger is None:
        logger = logging.getLogger(__name__)
    if servers is None:
        servers = {}
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]

        if summary:
            ws = run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")
            redis = run_ssh(shost, "ss -tnp | grep 6379 | grep ESTAB | wc -l")
            sessions = run_ssh(
                shost,
                "grep -c 'session_start' /var/log/lima/access.log 2>/dev/null"
                " || tail -1 /var/log/lima/app.log 2>/dev/null | grep -c session || echo '0'",
            )
            results.append(
                f"[{label}] ws:{(ws or '').strip() or '0'}"
                f" redis:{(redis or '').strip() or '0'}"
                f" sessions:{(sessions or '').strip() or '0'}"
            )
        else:
            results.append(f"\n=== {label} ({shost}) ===")
            ws = run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")
            if ws:
                results.append(f"  WebSocket: {ws.strip()}")
            redis = run_ssh(shost, "ss -tnp | grep 6379 | grep ESTAB | wc -l")
            if redis:
                results.append(f"  Redis: {redis.strip()}")
            sessions = run_ssh(
                shost,
                "grep -c 'session_start' /var/log/lima/access.log 2>/dev/null"
                " || grep -c 'session' /var/log/lima/app.log 2>/dev/null || echo 'N/A'",
            )
            if sessions and sessions != "N/A":
                results.append(f"  今日会话: {sessions.strip()}")
            fds = run_ssh(shost, "lsof -i :8080 2>/dev/null | wc -l || echo 'N/A'")
            if fds and fds != "N/A":
                results.append(f"  端口 8080 fd: {fds.strip()}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_tail_log(
    module: str,
    lines: int = 30,
    host: str | None = None,
    summary: bool = True,
    run_ssh=None,
    servers: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """按模块查看实时日志"""
    if logger is None:
        logger = logging.getLogger(__name__)
    if servers is None:
        servers = {}
    results = []

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

        if summary:
            found = False
            for lp in log_paths:
                exists = run_ssh(shost, f"test -f {lp} && echo 'yes' || echo 'no'")
                if exists and "yes" in exists:
                    total = run_ssh(shost, f"wc -l < {lp}")
                    errors = run_ssh(
                        shost, f"grep -ci 'error\\|exception\\|traceback' {lp} || echo 0"
                    )
                    results.append(
                        f"[{label}/{module}] total_lines:{total.strip() or '?'}"
                        f" error_lines:{errors.strip() or '0'}"
                        f" set summary=False to expand"
                    )
                    found = True
                    break
            if not found:
                results.append(f"[{label}/{module}] (no log file)")
        else:
            results.append(f"\n=== {label} ({shost}) ===")
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
                journal = run_ssh(
                    shost, f"journalctl -u lima* --no-pager -n {lines} 2>/dev/null || echo 'no journal'"
                )
                if journal and "no journal" not in journal:
                    results.append(f"  journald:")
                    results.append(journal)
                else:
                    results.append(f"  (未找到日志文件)")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_health_check(
    host: str | None = None,
    summary: bool = True,
    run_ssh=None,
    servers: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """关键端点健康检查"""
    if logger is None:
        logger = logging.getLogger(__name__)
    if servers is None:
        servers = {}
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]

        if summary:
            health = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || echo 'N/A'",
            )
            models = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/v1/models 2>/dev/null || echo 'N/A'",
            )
            device = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/device/v1/status 2>/dev/null || echo 'N/A'",
            )
            ok_count = sum(1 for c in [health, models, device] if c in ("200", "204"))
            results.append(
                f"[{label}] /health:{health} /models:{models} /device:{device} | ok:{ok_count}/3"
            )
        else:
            results.append(f"\n=== {label} ({shost}) ===")
            health = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code} %{time_total}s'"
                " http://localhost:8080/health 2>/dev/null || echo 'N/A'",
            )
            if health and health != "N/A":
                code, t = health.split()
                results.append(f"  {'OK' if code in ('200', '204') else 'FAIL'} /health: {code} ({t}s)")
            models = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/v1/models 2>/dev/null || echo 'N/A'",
            )
            if models and models != "N/A":
                results.append(f"  {'OK' if models in ('200', '204') else 'FAIL'} /v1/models: {models}")
            device = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/device/v1/status 2>/dev/null || echo 'N/A'",
            )
            if device and device != "N/A":
                results.append(f"  {'OK' if device == '200' else 'WARN'} /device/v1/status: {device}")
            ssl = run_ssh(
                shost,
                "curl -sk -o /dev/null -w '%{http_code}' https://localhost:443/health 2>/dev/null || echo 'N/A'",
            )
            if ssl and ssl != "N/A":
                results.append(f"  {'OK' if ssl == '200' else 'WARN'} SSL: {ssl}")

    return "\n".join(results) if results else "⚠️ 无可用服务器"


def tool_restart_service(
    service: str = "lima",
    host: str | None = None,
    run_ssh=None,
    servers: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """安全重启 LiMa 服务（带健康检查）"""
    if logger is None:
        logger = logging.getLogger(__name__)
    if servers is None:
        servers = {}
    results = []

    for shost, info in servers.items():
        if host and host not in shost and host not in info.get("label", ""):
            continue

        label = info["label"]
        results.append(f"\n=== {label} ({shost}) ===")

        # 检查当前状态
        current = run_ssh(
            shost,
            f"systemctl is-active {service} 2>/dev/null"
            f" || supervisorctl status {service} 2>/dev/null || echo 'unknown'",
        )
        results.append(f"  当前状态: {current}")

        # 重启
        results.append(f"  🔄 重启 {service}...")
        run_ssh(
            shost,
            f"systemctl restart {service} 2>/dev/null"
            f" || supervisorctl restart {service} 2>/dev/null"
            f" || docker restart {service} 2>/dev/null || echo 'restart attempted'",
        )

        # 等待启动
        time.sleep(3)

        # 健康检查
        healthy = False
        for _ in range(5):
            check = run_ssh(
                shost,
                "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || echo 'N/A'",
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
