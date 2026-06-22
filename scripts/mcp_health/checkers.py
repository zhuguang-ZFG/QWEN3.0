"""MCP server health checkers."""

from __future__ import annotations

import ast
import os
import time
from pathlib import Path
from typing import Any

from scripts.mcp_health.config import MCPHealth


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


def _check_config_only_mcp(name: str, cfg: dict[str, Any]) -> MCPHealth:
    """Check an MCP server that has no command (HTTP or inline tools)."""
    health = MCPHealth(name=name)

    if cfg.get("type") == "http":
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
    return health


def _check_python_mcp(name: str, args: list[str]) -> MCPHealth:
    """Check a Python-based MCP server (script or npx wrapper)."""
    health = MCPHealth(name=name)

    py_args = [a for a in args if a.endswith(".py")]
    if py_args and Path(py_args[0]).exists():
        health.ok = True
        health.tools = _count_python_tools(Path(py_args[0]))
    else:
        health.ok = True
        health.tools = 0

    pkg = _parse_npx_package(args)
    if pkg:
        health.ok = True
        health.tools = _estimate_tools(name, pkg)
    else:
        health.error = "Could not identify npx package"

    return health


def _check_node_mcp(name: str, args: list[str]) -> MCPHealth:
    """Check a Node-based MCP server."""
    js_file = args[0] if args and args[0].endswith(".js") else None
    if js_file and Path(js_file).exists():
        return MCPHealth(name=name, ok=True, tools=_estimate_tools(name, os.path.basename(js_file)))
    if args and os.path.exists(args[0]):
        return MCPHealth(name=name, ok=True)
    return MCPHealth(name=name, error=f"Script not found: {args[0] if args else ''}")


def _check_uvx_mcp(name: str, args: list[str]) -> MCPHealth:
    """Check a uvx-based MCP server."""
    return MCPHealth(name=name, ok=True, tools=_estimate_tools(name, args[0] if args else name))


def _check_generic_mcp(name: str) -> MCPHealth:
    """Check an MCP server with an unrecognized command."""
    return MCPHealth(name=name, ok=True, tools=_estimate_tools(name, name))


def _check_single_mcp_server(name: str, cfg: dict[str, Any]) -> MCPHealth:
    """Check one MCP server and return its health status."""
    cmd = cfg.get("command", "")
    args = cfg.get("args", [])

    if not cmd:
        return _check_config_only_mcp(name, cfg)
    if cmd.endswith(".py") or cmd == "python" or cmd == "python3":
        return _check_python_mcp(name, args)
    if cmd == "node" or cmd.endswith("node.exe"):
        return _check_node_mcp(name, args)
    if cmd == "uvx":
        return _check_uvx_mcp(name, args)
    return _check_generic_mcp(name)


def check_mcp_servers(servers: dict[str, dict[str, Any]]) -> list[MCPHealth]:
    """Check all MCP servers."""
    results: list[MCPHealth] = []

    for name, cfg in sorted(servers.items()):
        start = time.time()
        try:
            health = _check_single_mcp_server(name, cfg)
        except Exception as e:
            health = MCPHealth(name=name, error=str(e))
        health.latency_ms = round((time.time() - start) * 1000, 1)
        results.append(health)

    return results
