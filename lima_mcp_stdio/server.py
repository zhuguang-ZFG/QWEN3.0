"""Stdio MCP entry — MiMo Agent modes for Cursor (global or per-repo)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lima_mcp_stdio import mimo_agents, mimo_runner as mr

mcp = FastMCP(
    "lima-mimo",
    instructions=(
        "MiMo Agent MCP: review, verify, plan, security, tdd modes. "
        "Uses mimo run with compose skill prompts, git brief, and JSON findings. "
        "Set MIMO_MCP_WORKSPACE or open a folder; never on LiMa production server hot path."
    ),
)


@mcp.tool()
def lima_mimo_status(workspace: str = "") -> dict:
    """Check MiMo CLI, workspace, available modes, and last findings.json summary."""
    return mr.status(workspace=workspace or None)


@mcp.tool()
def lima_mimo_agents() -> dict:
    """List MiMo MCP modes (review / verify / plan / security / tdd) and skill hints."""
    return {"modes": mimo_agents.list_modes()}


@mcp.tool()
def lima_mimo_review(task: str, scope: str = "", workspace: str = "", timeout_seconds: int = 180) -> dict:
    """Run MiMo **review** mode: quality gate with JSON findings."""
    return mr.review(
        task=task,
        scope=scope or None,
        workspace=workspace or None,
        timeout=timeout_seconds,
    )


@mcp.tool()
def lima_mimo_verify(task: str = "", scope: str = "", workspace: str = "", timeout_seconds: int = 180) -> dict:
    """Run MiMo **verify** mode and diff against previous findings.json."""
    return mr.verify(
        task=task or None,
        scope=scope or None,
        workspace=workspace or None,
        timeout=timeout_seconds,
    )


@mcp.tool()
def lima_mimo_plan(task: str, scope: str = "", workspace: str = "", timeout_seconds: int = 180) -> dict:
    """Run MiMo **plan** mode: read-only execution plan (no file edits)."""
    return mr.run(
        task=task,
        mode="plan",
        scope=scope or None,
        workspace=workspace or None,
        timeout=timeout_seconds,
        json_findings=False,
    )


@mcp.tool()
def lima_mimo_run(
    task: str,
    mode: str = "review",
    scope: str = "",
    workspace: str = "",
    timeout_seconds: int = 180,
) -> dict:
    """Generic MiMo run: mode in review|verify|plan|security|tdd."""
    return mr.run(
        task=task,
        mode=mode,
        scope=scope or None,
        workspace=workspace or None,
        timeout=timeout_seconds,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
