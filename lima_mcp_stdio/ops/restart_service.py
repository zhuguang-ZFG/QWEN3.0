"""Restart service tool for Lima ops."""

from __future__ import annotations

import logging
import time

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


def _check_service_status(run_ssh, shost: str, service: str) -> str:
    return run_ssh(
        shost,
        f"systemctl is-active {service} 2>/dev/null || supervisorctl status {service} 2>/dev/null || echo 'unknown'",
    )


def _perform_restart(run_ssh, shost: str, service: str) -> None:
    run_ssh(
        shost,
        f"systemctl restart {service} 2>/dev/null"
        f" || supervisorctl restart {service} 2>/dev/null"
        f" || docker restart {service} 2>/dev/null || echo 'restart attempted'",
    )


def _wait_for_health(run_ssh, shost: str) -> bool:
    time.sleep(3)
    for _ in range(5):
        check = run_ssh(
            shost,
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || echo 'N/A'",
        )
        if check and check in ("200", "204"):
            return True
        time.sleep(2)
    return False


def _restart_one_server(run_ssh, shost: str, label: str, service: str) -> list[str]:
    results = [_format_result(label, shost, summary=False)]
    results.append(f"  当前状态: {_check_service_status(run_ssh, shost, service)}")
    results.append(f"  🔄 重启 {service}...")
    _perform_restart(run_ssh, shost, service)
    if _wait_for_health(run_ssh, shost):
        results.append(f"  ✅ {service} 重启成功")
    else:
        results.append(f"  ⚠️ 健康检查失败，请手动确认")
    return results


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
    results: list[str] = []

    for shost, info in _filter_servers(servers, host).items():
        results.extend(_restart_one_server(run_ssh, shost, info["label"], service))

    return "\n".join(results) if results else "⚠️ 无可用服务器"
