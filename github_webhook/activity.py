"""Classify GitHub webhook events for activity buffer."""

from __future__ import annotations


def classify_github_event(event: str, payload: dict) -> tuple[str, str]:
    repo = str(payload.get("repository", {}).get("full_name") or "")
    if event == "push":
        return "push", repo
    if event == "pull_request":
        return "pr", repo
    if event == "issues":
        return "issue", repo
    if event == "release":
        return "release", repo
    if event == "workflow_run":
        run = payload.get("workflow_run") or {}
        if str(run.get("conclusion") or "") not in {"", "success"}:
            return "ci_fail", repo
    return "other", repo
