"""Telegram /ci command — query GitHub CI evidence from mobile."""

from __future__ import annotations

import telegram_bot
from lima_mcp.github_tools import (
    get_combined_status,
    get_workflow_run,
    list_workflow_jobs,
    list_workflow_runs,
)


async def cmd_ci(chat_id: str, args: str) -> None:
    """Usage: /ci owner/repo [branch] — show latest CI status."""
    parts = args.strip().split()
    if not parts:
        await telegram_bot.send_message(
            "/ci owner/repo [branch]\nExample: /ci zhuguang-ZFG/QWEN3.0 codex/free-web-ai-probe",
            chat_id=chat_id, parse_mode="",
        )
        return

    repo_slug = parts[0].strip()
    branch = parts[1].strip() if len(parts) > 1 else "main"

    # Parse owner/repo
    slug_parts = repo_slug.split("/")
    if len(slug_parts) != 2:
        await telegram_bot.send_message("Format: owner/repo", chat_id=chat_id, parse_mode="")
        return
    owner, repo = slug_parts

    # Fetch workflow runs
    runs_result = list_workflow_runs(owner, repo, branch=branch, per_page=5)
    if not runs_result.get("ok"):
        await telegram_bot.send_message(
            f"CI query failed: {runs_result.get('error', 'unknown')}",
            chat_id=chat_id, parse_mode="",
        )
        return

    runs = runs_result.get("runs", [])
    if not runs:
        await telegram_bot.send_message(
            f"No CI runs for `{owner}/{repo}`@{branch}", chat_id=chat_id, parse_mode="Markdown",
        )
        return

    # Format latest runs
    lines = [f"*CI: `{owner}/{repo}`@{branch}*", ""]
    for r in runs[:5]:
        icon = "✅" if r["conclusion"] == "success" else ("❌" if r["conclusion"] == "failure" else "⏳")
        sha = r["sha"]
        name = r["name"]
        lines.append(f"{icon} `{sha}` {name}")

    # Get combined status for branch
    status_result = get_combined_status(owner, repo, branch)
    if status_result.get("ok"):
        state = status_result["state"]
        state_icon = {"success": "✅", "failure": "❌", "pending": "⏳"}.get(state, "❓")
        lines.append(f"")
        lines.append(f"Branch status: {state_icon} *{state}*")

    lines.append(f"")
    lines.append(f"`/ci {repo_slug} {branch} <run_id>` for job details")

    await telegram_bot.send_message("\n".join(lines), chat_id=chat_id, parse_mode="Markdown")


async def cmd_ci_detail(chat_id: str, args: str) -> None:
    """Show detailed job/step info for a specific run."""
    parts = args.strip().split()
    if len(parts) < 3:
        await telegram_bot.send_message("/ci owner/repo branch run_id", chat_id=chat_id, parse_mode="")
        return

    repo_slug = parts[0]
    slug_parts = repo_slug.split("/")
    if len(slug_parts) != 2:
        return
    owner, repo = slug_parts
    try:
        run_id = int(parts[2])
    except ValueError:
        await telegram_bot.send_message("run_id must be integer", chat_id=chat_id, parse_mode="")
        return

    jobs_result = list_workflow_jobs(owner, repo, run_id)
    if not jobs_result.get("ok"):
        await telegram_bot.send_message(f"Failed: {jobs_result.get('error')}", chat_id=chat_id, parse_mode="")
        return

    run_result = get_workflow_run(owner, repo, run_id)
    run_name = run_result.get("name", "CI") if run_result.get("ok") else "CI"
    conclusion = run_result.get("conclusion", "?") if run_result.get("ok") else "?"

    lines = [f"*{run_name}* `{owner}/{repo}`", f"Conclusion: *{conclusion}*", ""]

    for j in jobs_result.get("jobs", []):
        j_icon = "✅" if j["conclusion"] == "success" else ("❌" if j["conclusion"] == "failure" else "⏳")
        lines.append(f"{j_icon} *{j['name']}* ({j['conclusion']})")
        for s in j.get("steps", []):
            s_icon = "✅" if s["conclusion"] == "success" else ("❌" if s["conclusion"] == "failure" else "⬜")
            if s["status"] == "completed":
                lines.append(f"   {s_icon} {s['name']}")

    text = "\n".join(lines)[:4000]
    await telegram_bot.send_message(text, chat_id=chat_id, parse_mode="Markdown")
