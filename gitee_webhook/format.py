"""Format Gitee WebHook payloads into Telegram-safe summaries."""

from __future__ import annotations


def _short_sha(sha: str) -> str:
    return (sha or "")[:7]


def _branch_from_ref(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    if ref.startswith("refs/tags/"):
        return ref[len("refs/tags/"):]
    return ref or "unknown"


def _repo_name(payload: dict) -> str:
    repo = payload.get("repository") or {}
    return str(
        repo.get("path_with_namespace")
        or repo.get("full_name")
        or "unknown"
    )


def format_gitee_event(event_header: str, payload: dict) -> str | None:
    hook = str(payload.get("hook_name") or "")
    event = (event_header or hook).lower()

    if hook == "push_hooks" or "push" in event:
        return _format_push(payload)
    if hook == "merge_request_hooks" or "merge request" in event:
        return _format_merge_request(payload)
    if hook == "tag_push_hooks" or "tag push" in event:
        return _format_tag_push(payload)
    return None


def extract_push_shas(payload: dict) -> list[str]:
    shas: list[str] = []
    after = str(payload.get("after") or "")
    if after and after != "0" * 40:
        shas.append(after)
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
    return list(dict.fromkeys(shas))


def _format_push(payload: dict) -> str | None:
    repo = _repo_name(payload)
    ref = str(payload.get("ref") or "")
    branch = _branch_from_ref(ref)
    commits = payload.get("commits") or []
    count = len(commits) or int(payload.get("total_commits_count") or 0)
    if count == 0 and payload.get("head_commit"):
        count = 1
    if count == 0 and not payload.get("after"):
        return None
    latest = ""
    if commits:
        latest = str(commits[-1].get("id") or "")
    elif isinstance(payload.get("head_commit"), dict):
        latest = str(payload["head_commit"].get("id") or "")
    else:
        latest = str(payload.get("after") or "")
    sender = payload.get("sender") or {}
    pusher = str(sender.get("name") or sender.get("username") or sender.get("login") or "unknown")
    return (
        f"Gitee push `{repo}`@{branch}\n"
        f"{count} commit(s), latest `{_short_sha(latest)}` by {pusher}"
    )


def _format_tag_push(payload: dict) -> str | None:
    repo = _repo_name(payload)
    tag = _branch_from_ref(str(payload.get("ref") or ""))
    latest = str(payload.get("after") or "")
    return f"Gitee tag `{repo}` → `{tag}` (`{_short_sha(latest)}`)"


def _format_merge_request(payload: dict) -> str | None:
    pr = payload.get("pull_request") or {}
    state = str(pr.get("state") or "updated")
    if pr.get("merged") is True:
        state = "merged"
    number = pr.get("number", "?")
    title = str(pr.get("title") or "")[:120]
    head = str((pr.get("head") or {}).get("ref") or "")
    base = str((pr.get("base") or {}).get("ref") or "")
    repo = _repo_name(payload)
    return f"Gitee MR `{repo}` #{number} {state}\n{title}\n{head} → {base}"
