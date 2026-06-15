"""Stdio MCP entry — exposes MiMo review tools to Cursor (local dev only)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lima_mcp_stdio import mimo_runner as mr

mcp = FastMCP(
    "lima-mimo",
    instructions=(
        "LiMa MiMo review lane. Runs offline `mimo run` via lima-multi-cli skill. "
        "Never used on LiMa production hot path."
    ),
)


@mcp.tool()
def lima_mimo_status() -> dict:
    """Check MiMo CLI on PATH and summarize the last findings.json artifact."""
    return mr.status()


@mcp.tool()
def lima_mimo_review(task: str, scope: str = "", timeout_seconds: int = 180) -> dict:
    """Run MiMo code review for a task. Optional scope is a repo-relative file or directory."""
    return mr.review(task=task, scope=scope or None, timeout=timeout_seconds)


@mcp.tool()
def lima_mimo_verify(task: str = "", scope: str = "", timeout_seconds: int = 180) -> dict:
    """Re-run MiMo review and compare with the previous findings.json (closed / still_open / new)."""
    return mr.verify(
        task=task or None,
        scope=scope or None,
        timeout=timeout_seconds,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
