"""Optional GitHub issue → agent task bridge (TG-GH-5, default off)."""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


def auto_task_enabled() -> bool:
    return os.environ.get("GITHUB_WEBHOOK_AUTO_TASK", "0").strip().lower() in {"1", "true", "yes"}


def maybe_create_task_from_issue(payload: dict) -> str | None:
    """Create agent task when issue opened; returns task_id or None."""
    if not auto_task_enabled():
        return None
    if str(payload.get("action") or "") != "opened":
        return None
    issue = payload.get("issue") or {}
    if not isinstance(issue, dict):
        return None
    number = issue.get("number")
    title = str(issue.get("title") or "").strip()
    if not title:
        return None
    repo = str(payload.get("repository", {}).get("full_name") or "local")
    html_url = str(issue.get("html_url") or "")
    goal = f"GitHub issue #{number}: {title}"[:500]
    constraints = [f"github_issue={number}", f"github_repo={repo}"]
    if html_url:
        constraints.append(f"github_url={html_url[:240]}")
    try:
        from routes.agent_task_schemas import TaskCreateBody
        from routes.agent_task_service import create_task_from_body

        created = create_task_from_body(TaskCreateBody(
            repo=repo.split("/")[-1] if "/" in repo else repo,
            branch="main",
            goal=goal,
            constraints=constraints,
            mode="plan",
        ))
        task_id = str(created.get("task_id") or "")
        if task_id:
            logger.info("github auto_task created task_id=%s issue=%s", task_id, number)
        return task_id or None
    except Exception as exc:
        logger.exception("github auto_task failed issue=%s", number)
        return None
