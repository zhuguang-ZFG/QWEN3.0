#!/usr/bin/env python3
"""Smoke: Gitee tools exposed via MCP + dev_tools."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from lima_mcp import TOOL_DEFINITIONS
from lima_mcp.tools import handle_tool_call


def main() -> int:
    names = {tool["name"] for tool in TOOL_DEFINITIONS}
    required = {"dev_search_gitee", "dev_fetch_gitee_file"}
    missing = required - names
    if missing:
        print(f"smoke_gitee_mcp_fail missing_tools={sorted(missing)}")
        return 1

    skipped = handle_tool_call("dev_search_gitee", {"query": "routing_engine", "max_results": 2})
    if skipped.get("skipped"):
        print("smoke_gitee_mcp_fail token_missing_after_provision")
        return 1
    if not skipped.get("ok"):
        print(f"smoke_gitee_mcp_fail search err={skipped.get('error', '')[:120]}")
        return 1

    fetch = handle_tool_call(
        "dev_fetch_gitee_file",
        {"repo": "zhuguang-cn/QWEN3.0", "path": "STATUS.md", "max_chars": 400},
    )
    if fetch.get("skipped"):
        print("smoke_gitee_mcp_fail token_missing_after_provision")
        return 1
    if not fetch.get("ok"):
        print(f"smoke_gitee_mcp_fail fetch err={fetch.get('error', '')[:120]}")
        return 1
    if not str(fetch.get("text") or "").strip():
        print("smoke_gitee_mcp_fail fetch_empty")
        return 1

    print("smoke_gitee_mcp_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
