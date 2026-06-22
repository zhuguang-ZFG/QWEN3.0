"""MCP health check reporting and notifications."""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

from scripts.mcp_health.config import MCPHealth, TOAST_SCRIPT


def print_report(results: list[MCPHealth], source_count: int):
    """Print formatted report."""
    failed = [r for r in results if not r.ok]
    total = len(results)

    print(f"\n{'=' * 55}")
    print(f"  LiMa MCP Health Check  —  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'=' * 55}")
    print(f"  MCP servers: {total}  |  OK: {total - len(failed)}  |  FAIL: {len(failed)}")
    print()

    for r in results:
        status = "✅" if r.ok else "❌"
        tools = f" [{r.tools}tools]" if r.ok else ""
        err = f"  {r.error}" if r.error else ""
        print(f"  {status} {r.name:25s}  {r.latency_ms:6.1f}ms{tools}{err}")

    if failed:
        print(f"\n  ❌ FAILED ({len(failed)}):")
        for r in failed:
            print(f"     {r.name}: {r.error}")

    return len(failed)


def show_toast(title: str, msg: str):
    """Fire Windows desktop notification."""
    if not TOAST_SCRIPT.exists():
        return
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(TOAST_SCRIPT),
                "-Title",
                title,
                "-Message",
                msg,
            ],
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass
