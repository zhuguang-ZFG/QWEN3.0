"""Tail log tool for Lima ops."""

from __future__ import annotations

import logging

from lima_mcp_stdio.ops._helpers import _filter_servers, _format_result


def _tail_summary(shost, label, module, log_paths, run_ssh, results):
    """Collect summary info for one server's log files."""
    found = False
    for lp in log_paths:
        exists = run_ssh(shost, f"test -f {lp} && echo 'yes' || echo 'no'")
        if exists and "yes" in exists:
            total = run_ssh(shost, f"wc -l < {lp}")
            errors = run_ssh(shost, f"grep -ci 'error\\|exception\\|traceback' {lp} || echo 0")
            results.append(
                _format_result(
                    f"{label}/{module}",
                    shost,
                    f"total_lines:{total.strip() or '?'}"
                    f" error_lines:{errors.strip() or '0'}"
                    f" set summary=False to expand",
                    summary=True,
                )
            )
            found = True
            break
    if not found:
        results.append(_format_result(f"{label}/{module}", shost, "(no log file)", summary=True))


def _tail_full(shost, label, module, lines, log_paths, run_ssh, results):
    """Collect full log tail for one server."""
    results.append(_format_result(label, shost, summary=False))
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
        journal = run_ssh(shost, f"journalctl -u lima* --no-pager -n {lines} 2>/dev/null || echo 'no journal'")
        if journal and "no journal" not in journal:
            results.append(f"  journald:")
            results.append(journal)
        else:
            results.append(f"  (未找到日志文件)")


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
    results = []

    log_paths = [
        f"/var/log/lima/{module}.log",
        f"/var/log/lima/app.log",
        f"/opt/lima/logs/{module}.log",
        f"/root/lima/logs/latest.log",
    ]

    for shost, info in _filter_servers(servers, host).items():
        label = info["label"]
        if summary:
            _tail_summary(shost, label, module, log_paths, run_ssh, results)
        else:
            _tail_full(shost, label, module, lines, log_paths, run_ssh, results)

    return "\n".join(results) if results else "⚠️ 无可用服务器"
