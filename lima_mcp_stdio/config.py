"""LiMa MCP stdio configuration (lazy reads for testability)."""

from __future__ import annotations

import os


def mimo_binary() -> str:
    return os.environ.get("MIMO_MCP_MIMO_BINARY", "")


def mimo_model() -> str:
    return os.environ.get("MIMO_MCP_MODEL", "").strip()


def skip_permissions() -> bool:
    return os.environ.get("MIMO_MCP_SKIP_PERMISSIONS", "").strip().lower() in {"1", "true", "yes"}


def workspace() -> str:
    return os.environ.get("MIMO_MCP_WORKSPACE", "").strip()


def timeout() -> int:
    raw = os.environ.get("LIMA_TIMEOUT", os.environ.get("MIMO_MCP_TIMEOUT", "180") or "180")
    try:
        return max(30, int(raw))
    except ValueError:
        return 180


def artifact_dir() -> str:
    return os.environ.get("MIMO_MCP_ARTIFACT_DIR", "").strip()


def agent() -> str:
    return os.environ.get("MIMO_MCP_AGENT", "").strip()
