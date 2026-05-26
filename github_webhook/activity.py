"""Classify GitHub webhook events for activity buffer."""

from __future__ import annotations


def classify_github_event(event: str, payload: dict) -> tuple[str, str]:
    if event == "push":
        return "push", str(payload.get("repository", {}).get("full_name") or "")
    if event == "pull_request":
        return "pr", str(payload.get("repository", {}).get("full_name") or "")
    if event == "workflow_run":
        run = payload.get("workflow_run") or {}
        if str(run.get("conclusion") or "") not in {"", "success"}:
            return "ci_fail", str(payload.get("repository", {}).get("full_name") or "")
    return "other", str(payload.get("repository", {}).get("full_name") or "")
