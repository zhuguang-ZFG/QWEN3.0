#!/usr/bin/env python3
"""
LiMa MCP 健康巡检 — 验证所有 MCP 服务器在线可用。

用法:
  python scripts/check_mcp_health.py
  python scripts/check_mcp_health.py --notify     # 异常时弹 toast
"""

from __future__ import annotations

# 修复 GBK 终端下的 emoji 输出崩溃（Windows 默认终端 + cron 环境）
import io
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.upper() == "GBK":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mcp_health.config import REPORT_DIR, check_symmetry, load_mcp_configs
from scripts.mcp_health.checkers import check_mcp_servers
from scripts.mcp_health.report import print_report, show_toast


def main():
    notify = "--notify" in sys.argv

    print("🔍 MCP 健康巡检...")
    servers = load_mcp_configs()

    if not servers:
        print("❌ No MCP configurations found")
        return 1

    print(f"  发现 {len(servers)} 个 MCP 服务器配置")
    results = check_mcp_servers(servers)
    failed = print_report(results, len(servers))

    # Symmetry check
    cursor_s, kimi_s = check_symmetry(servers)
    only_cursor = cursor_s - kimi_s
    only_kimi = kimi_s - cursor_s
    if only_cursor or only_kimi:
        print(f"\n  ⚠️  MCP 不对称:")
        if only_cursor:
            print(f"     仅在 Cursor: {', '.join(sorted(only_cursor))}")
        if only_kimi:
            print(f"     仅在 Kimi: {', '.join(sorted(only_kimi))}")
    else:
        print(f"\n  ✅ MCP 完全对称 ({len(cursor_s)})")

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "ok": len(results) - failed,
        "failed": failed,
        "servers": {r.name: {"ok": r.ok, "error": r.error, "latency_ms": r.latency_ms} for r in results},
        "cursor_mcp_count": len(cursor_s),
        "kimi_mcp_count": len(kimi_s),
    }
    (REPORT_DIR / "mcp-health.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Toast for failures
    if failed and notify:
        names = [r.name for r in results if not r.ok]
        show_toast(f"🔴 MCP 异常: {failed}/{len(results)}", f"异常: {', '.join(names[:3])}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
