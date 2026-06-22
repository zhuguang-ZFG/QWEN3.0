"""Server status tool for Lima ops."""

from __future__ import annotations

import logging
import re

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


def _status_summary(shost, label, run_ssh, results):
    """Collect summary status metrics for one server."""
    uptime = run_ssh(shost, "uptime | sed 's/.*up//;s/,.*//'")
    mem = run_ssh(shost, 'free -h | awk \'NR==2{print "mem:"$3"/"$2}\'')
    cpu = run_ssh(shost, "top -bn1 | grep 'Cpu(s)' | awk '{print \"cpu:\"$2\"%\"}'")
    proc_count = run_ssh(shost, "ps aux | grep -E 'python|uvicorn|gunicorn' | grep -v grep | wc -l")
    ver = run_ssh(shost, "cat /opt/lima/VERSION 2>/dev/null || echo 'N/A'")
    docker_count = run_ssh(shost, "docker ps -q 2>/dev/null | wc -l")
    ws_count = run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")
    results.append(
        _format_result(
            label,
            shost,
            f"uptime:{uptime or '?'} | mem:{mem or '?'} | cpu:{cpu or '?'} | "
            f"proc:{(proc_count or '').strip() or '0'} | ver:{ver or 'N/A'} | "
            f"docker:{(docker_count or '').strip() or '0'} | ws:{(ws_count or '').strip() or '0'}",
            summary=True,
        )
    )


def _status_detail(shost, label, run_ssh, results):
    """Collect detailed status for one server."""
    results.append(_format_result(label, shost, summary=False))
    uptime = run_ssh(shost, "uptime")
    if uptime:
        results.append(f"  Uptime: {uptime}")
    lima_procs = run_ssh(shost, "ps aux | grep -E 'python|uvicorn|gunicorn' | grep -v grep || echo '无'")
    if lima_procs:
        for line in lima_procs.split("\n")[:10]:
            line = re.sub(r"\s+", " ", line.strip())
            if line and line != "无":
                results.append(f"  {line}")
    mem = run_ssh(shost, "free -h | head -2")
    if mem:
        results.append(f"  {mem}")
    ver = run_ssh(
        shost,
        "cat /opt/lima/VERSION 2>/dev/null || cat /root/lima/VERSION 2>/dev/null || echo 'N/A'",
    )
    if ver:
        results.append(f"  Version: {ver}")
    docker = run_ssh(shost, "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'no docker'")
    if docker:
        for d in docker.split("\n"):
            results.append(f"  Docker: {d}")


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
    results = []

    for shost, info in _filter_servers(servers, host).items():
        label = info["label"]
        if summary:
            _status_summary(shost, label, run_ssh, results)
        else:
            _status_detail(shost, label, run_ssh, results)

    return "\n".join(results) if results else "⚠️ 无可用服务器"
