"""Format GitHub webhook payloads into Telegram-safe summaries."""

from __future__ import annotations


def _short_sha(sha: str) -> str:
    return (sha or "")[:7]


def _branch_from_ref(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    return ref or "unknown"


def format_github_event(event: str, payload: dict) -> str | None:
    """Return a one-line summary or None if the event should be ignored."""
    if event == "push":
        return _format_push(payload)
    if event == "pull_request":
        return _format_pull_request(payload)
    if event == "workflow_run":
        return _format_workflow_run(payload)
    return None


def _format_push(payload: dict) -> str | None:
    repo = str(payload.get("repository", {}).get("full_name") or "unknown")
    ref = str(payload.get("ref") or "")
    branch = _branch_from_ref(ref)
    commits = payload.get("commits") or []
    if not commits and payload.get("head_commit"):
        commits = [payload["head_commit"]]
    count = len(commits)
    if count == 0:
        return None
    latest = str(commits[-1].get("id") or "")
    pusher = str(payload.get("pusher", {}).get("name") or "unknown")
    return (
        f"GitHub push `{repo}`@{branch}\n"
        f"{count} commit(s), latest `{_short_sha(latest)}` by {pusher}"
    )


def _format_pull_request(payload: dict) -> str | None:
    action = str(payload.get("action") or "")
    if action not in {"opened", "closed", "reopened", "ready_for_review", "merged"}:
        return None
    pr = payload.get("pull_request") or {}
    number = pr.get("number", "?")
    title = str(pr.get("title") or "")[:120]
    head = str(pr.get("head", {}).get("ref") or "")
    base = str(pr.get("base", {}).get("ref") or "")
    repo = str(payload.get("repository", {}).get("full_name") or "unknown")
    merged = pr.get("merged") is True
    label = "merged" if action == "closed" and merged else action
    return f"GitHub PR `{repo}` #{number} {label}\n{title}\n{head} → {base}"


def _format_workflow_run(payload: dict) -> str | None:
    if str(payload.get("action") or "") != "completed":
        return None
    run = payload.get("workflow_run") or {}
    conclusion = str(run.get("conclusion") or "unknown")
    if conclusion == "success":
        return None
    name = str(run.get("name") or "workflow")
    branch = str(run.get("head_branch") or "unknown")
    repo = str(payload.get("repository", {}).get("full_name") or "unknown")
    return f"GitHub CI `{repo}` FAILED\nWorkflow: {name} on `{branch}` ({conclusion})"
