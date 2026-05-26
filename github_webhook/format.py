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
    if event == "issues":
        return _format_issue(payload)
    if event == "release":
        return _format_release(payload)
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


def extract_github_push_shas(payload: dict) -> list[str]:
    shas: list[str] = []
    for commit in payload.get("commits") or []:
        if isinstance(commit, dict):
            cid = str(commit.get("id") or "")
            if cid:
                shas.append(cid)
    head = payload.get("head_commit") or {}
    if isinstance(head, dict):
        cid = str(head.get("id") or "")
        if cid:
            shas.append(cid)
    after = str(payload.get("after") or "")
    if after and after != "0" * 40:
        shas.append(after)
    return list(dict.fromkeys(shas))


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


def _format_issue(payload: dict) -> str | None:
    action = str(payload.get("action") or "")
    if action not in {"opened", "closed", "labeled", "reopened"}:
        return None
    issue = payload.get("issue") or {}
    number = issue.get("number", "?")
    title = str(issue.get("title") or "")[:120]
    repo = str(payload.get("repository", {}).get("full_name") or "unknown")
    label = payload.get("label") or {}
    label_name = str(label.get("name") or "") if action == "labeled" else ""
    suffix = f" label `{label_name}`" if label_name else ""
    url = str(issue.get("html_url") or "")
    line = f"GitHub issue `{repo}` #{number} {action}{suffix}\n{title}"
    if url:
        line += f"\n{url}"
    return line


def _format_release(payload: dict) -> str | None:
    if str(payload.get("action") or "") != "published":
        return None
    release = payload.get("release") or {}
    tag = str(release.get("tag_name") or release.get("name") or "?")
    name = str(release.get("name") or tag)[:80]
    repo = str(payload.get("repository", {}).get("full_name") or "unknown")
    url = str(release.get("html_url") or "")
    line = f"GitHub release `{repo}` {tag}\n{name}"
    if url:
        line += f"\n{url}"
    return line
