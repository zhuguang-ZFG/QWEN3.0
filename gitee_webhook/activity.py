"""Classify Gitee webhook events for activity buffer."""

from __future__ import annotations


def classify_gitee_event(event_header: str, payload: dict) -> tuple[str, str]:
    hook = str(payload.get("hook_name") or "")
    repo = str(
        (payload.get("repository") or {}).get("path_with_namespace")
        or (payload.get("repository") or {}).get("full_name")
        or ""
    )
    event = (event_header or hook).lower()
    if hook == "push_hooks" or "push" in event:
        return "push", repo
    if hook == "merge_request_hooks" or "merge request" in event:
        return "mr", repo
    return "other", repo
