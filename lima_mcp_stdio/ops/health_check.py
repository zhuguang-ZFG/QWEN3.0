"""Health check tool for Lima ops."""

from __future__ import annotations

import logging

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


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
    results = []

    for shost, info in _filter_servers(servers, host).items():
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
                _format_result(
                    label, shost, f"/health:{health} /models:{models} /device:{device} | ok:{ok_count}/3", summary=True
                )
            )
        else:
            results.append(_format_result(label, shost, summary=False))
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
