"""Device connections tool for Lima ops."""

from __future__ import annotations

import logging

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


def _count_ws(run_ssh, shost: str) -> str:
    return run_ssh(shost, "ss -tnp | grep -E ':8080|:8000' | grep ESTAB | wc -l")


def _count_redis(run_ssh, shost: str) -> str:
    return run_ssh(shost, "ss -tnp | grep 6379 | grep ESTAB | wc -l")


def _count_sessions(run_ssh, shost: str, summary: bool) -> str:
    if summary:
        return run_ssh(
            shost,
            "grep -c 'session_start' /var/log/lima/access.log 2>/dev/null"
            " || tail -1 /var/log/lima/app.log 2>/dev/null | grep -c session || echo '0'",
        )
    return run_ssh(
        shost,
        "grep -c 'session_start' /var/log/lima/access.log 2>/dev/null"
        " || grep -c 'session' /var/log/lima/app.log 2>/dev/null || echo 'N/A'",
    )


def _summary_for_host(run_ssh, shost: str, label: str) -> list[str]:
    ws = _count_ws(run_ssh, shost)
    redis = _count_redis(run_ssh, shost)
    sessions = _count_sessions(run_ssh, shost, summary=True)
    text = (
        f"ws:{(ws or '').strip() or '0'}"
        f" redis:{(redis or '').strip() or '0'}"
        f" sessions:{(sessions or '').strip() or '0'}"
    )
    return [_format_result(label, shost, text, summary=True)]


def _detail_for_host(run_ssh, shost: str, label: str) -> list[str]:
    results = [_format_result(label, shost, summary=False)]
    ws = _count_ws(run_ssh, shost)
    if ws:
        results.append(f"  WebSocket: {ws.strip()}")
    redis = _count_redis(run_ssh, shost)
    if redis:
        results.append(f"  Redis: {redis.strip()}")
    sessions = _count_sessions(run_ssh, shost, summary=False)
    if sessions and sessions != "N/A":
        results.append(f"  今日会话: {sessions.strip()}")
    fds = run_ssh(shost, "lsof -i :8080 2>/dev/null | wc -l || echo 'N/A'")
    if fds and fds != "N/A":
        results.append(f"  端口 8080 fd: {fds.strip()}")
    return results


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
    results: list[str] = []

    for shost, info in _filter_servers(servers, host).items():
        if summary:
            results.extend(_summary_for_host(run_ssh, shost, info["label"]))
        else:
            results.extend(_detail_for_host(run_ssh, shost, info["label"]))

    return "\n".join(results) if results else "⚠️ 无可用服务器"
