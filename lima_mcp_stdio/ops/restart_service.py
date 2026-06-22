"""Restart service tool for Lima ops."""

from __future__ import annotations

import logging
import time

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


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
    results = []

    for shost, info in _filter_servers(servers, host).items():
        label = info["label"]
        results.append(_format_result(label, shost, summary=False))

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
