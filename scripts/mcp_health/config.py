"""MCP health check configuration and shared dataclass."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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
