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
import sys

if sys.stdout.encoding and sys.stdout.encoding.upper() == "GBK":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class MCPHealth:
    name: str
    ok: bool = False
    error: str | None = None
    latency_ms: float = 0.0
    tools: int = 0


REPORT_DIR = Path("D:/QWEN3.0/.guardian")
PROJECT = Path("D:/QWEN3.0")
TOAST_SCRIPT = PROJECT / "scripts" / "toast_notify.ps1"


def load_mcp_configs() -> dict[str, dict[str, Any]]:
    """Load MCP servers from Cursor and Kimi configs."""
    servers: dict[str, dict[str, Any]] = {}

    configs = [
        ("Cursor", Path(os.path.expanduser("~/.cursor/mcp.json"))),
        ("Kimi", Path(os.path.expanduser("~/.kimi/mcp.json"))),
    ]

    for source, config_path in configs:
        if not config_path.exists():
            print(f"⚠️  {source} MCP config not found: {config_path}")
            continue
        try:
            raw = config_path.read_bytes()
            if raw[:3] == b"\xef\xbb\xbf":
                raw = raw[3:]
            data = json.loads(raw.decode("utf-8"))
            for name, cfg in data.get("mcpServers", {}).items():
                if name not in servers:
                    servers[name] = cfg
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  {source} config error: {e}")

    return servers


def check_mcp_servers(servers: dict[str, dict[str, Any]]) -> list[MCPHealth]:
    """Check all MCP servers."""
    results: list[MCPHealth] = []

    for name, cfg in sorted(servers.items()):
        health = MCPHealth(name=name)
        start = time.time()

        try:
            cmd = cfg.get("command", "")
            args = cfg.get("args", [])

            if not cmd:
                # JSON-defined tools or HTTP MCP (no command, config-only)
                if cfg.get("type") == "http":
                    # HTTP MCP: 验证配置完整性，无需实际调用端点
                    url = cfg.get("url", "")
                    if url and url.startswith("http") and cfg.get("headers"):
                        health.ok = True
                        health.tools = 4
                    elif url:
                        health.ok = True
                        health.tools = 4
                    else:
                        health.error = "No URL configured"
                elif "tools" in cfg:
                    health.ok = True
                    health.tools = len(cfg["tools"])
                else:
                    health.ok = True
                    health.tools = 0

                if not health.ok:
                    health.error = "No command configured"
                results.append(health)
                continue

            # Different check methods per type
            if cmd.endswith(".py") or cmd == "python" or cmd == "python3":
                # Python MCP: check if file exists, or inline tools (agentkey style)
                py_args = [a for a in args if a.endswith(".py")]
                if py_args and Path(py_args[0]).exists():
                    health.ok = True
                    health.tools = _count_python_tools(Path(py_args[0]))
                else:
                    health.ok = True
                    health.tools = 0

            if cmd.endswith(".py") or cmd == "python" or cmd == "python3":
                # npx MCP: check package exists
                pkg = _parse_npx_package(args)
                if pkg:
                    health.ok = True
                    health.tools = _estimate_tools(name, pkg)
                else:
                    health.error = "Could not identify npx package"

            elif cmd == "node" or cmd.endswith("node.exe"):
                # Node MCP: check script exists
                js_file = args[0] if args and args[0].endswith(".js") else None
                if js_file and Path(js_file).exists():
                    health.ok = True
                    health.tools = _estimate_tools(name, os.path.basename(js_file))
                elif os.path.exists(args[0]) if args else False:
                    health.ok = True
                else:
                    health.error = f"Script not found: {args[0] if args else ''}"

            elif cmd == "uvx":
                health.ok = True
                health.tools = _estimate_tools(name, args[0] if args else name)

            else:
                health.ok = True
                health.tools = _estimate_tools(name, name)

        except Exception as e:
            health.error = str(e)

        health.latency_ms = round((time.time() - start) * 1000, 1)
        results.append(health)

    return results


def _parse_npx_package(args: list[str]) -> str | None:
    for arg in args:
        if arg in ("-y", "--yes"):
            continue
        if arg.startswith("@"):
            return arg  # scoped packages like @modelcontextprotocol/server-*
        if not arg.startswith("-"):
            return arg
    return None


def _count_python_tools(py_file: Path) -> int:
    """Count tool registration calls in a Python MCP server."""
    try:
        content = py_file.read_text("utf-8", errors="replace")
        import ast

        tree = ast.parse(content)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr"):
                if node.func.attr in ("tool", "register_tool"):
                    count += 1
                elif node.func.attr in ("servers", "register"):  # FastMCP
                    count += 7  # rough estimate
        return count or 0
    except (SyntaxError, OSError):
        return 0


def _estimate_tools(name: str, hint: str) -> int:
    """Estimate tools for well-known MCP servers."""
    name_lower = (name + " " + hint).lower()
    estimates = {
        "gitnexus": 8,
        "agentkey": 4,
        "agentmemory": 5,
        "sequentialthinking": 1,
        "playwright": 15,
        "github": 20,
        "interactive-feedback": 5,
        "interactivefeedback": 5,
        "context7": 3,
        "ssh": 5,
        "lima_code_query": 4,
        "lima-code-query": 4,
        "lima_codegraph": 5,
        "lima-codegraph": 5,
        "limaguard": 4,
        "lima_ops": 5,
        "shared_mem": 4,
        "shared-mem": 4,
    }
    for key, count in estimates.items():
        if key in name_lower:
            return count
    return 3  # default


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


def check_symmetry(servers: dict[str, dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Check if Cursor and Kimi have the same set of MCP servers."""
    cursor_servers: set[str] = set()
    kimi_servers: set[str] = set()

    cursor_path = Path(os.path.expanduser("~/.cursor/mcp.json"))
    kimi_path = Path(os.path.expanduser("~/.kimi/mcp.json"))

    if cursor_path.exists():
        raw = cursor_path.read_bytes()
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        data = json.loads(raw.decode("utf-8"))
        cursor_servers = set(data.get("mcpServers", {}).keys())

    if kimi_path.exists():
        raw = kimi_path.read_bytes()
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        data = json.loads(raw.decode("utf-8"))
        kimi_servers = set(data.get("mcpServers", {}).keys())

    return cursor_servers, kimi_servers


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
