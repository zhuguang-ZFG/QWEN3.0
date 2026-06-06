"""Gitee webhook endpoint — push/MR summaries to Telegram."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from gitee_webhook.dedupe import record_push_shas, should_skip_gitee_push
from gitee_webhook.format import extract_push_shas, format_gitee_event
from gitee_webhook.verify import verify_gitee_request

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gitee")


def _is_enabled() -> bool:
    return os.environ.get("GITEE_WEBHOOK_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _get_secret() -> str:
    return os.environ.get("GITEE_WEBHOOK_SECRET", "").strip()


def _allowed_repos() -> set[str]:
    raw = os.environ.get("GITEE_WEBHOOK_REPOS", "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _repo_allowed(full_name: str) -> bool:
    allowlist = _allowed_repos()
    if not allowlist:
        return True
    return full_name.lower() in allowlist


def _repo_from_payload(payload: dict) -> str:
    repo = payload.get("repository") or {}
    return str(repo.get("path_with_namespace") or repo.get("full_name") or "")


@router.post("/webhook")
async def gitee_webhook(request: Request):
    if not _is_enabled():
        raise HTTPException(503, "Gitee webhook not enabled")
    secret = _get_secret()
    if not secret:
        raise HTTPException(503, "GITEE_WEBHOOK_SECRET not configured")

    body = await request.body()
    token_header = request.headers.get("X-Gitee-Token", "") or request.headers.get("x-gitee-token", "")
    timestamp_header = request.headers.get("X-Gitee-Timestamp", "") or request.headers.get("x-gitee-timestamp", "")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("gitee webhook invalid json")
        return {"ok": True, "ignored": True}

    if not isinstance(payload, dict):
        return {"ok": True, "ignored": True}

    if not verify_gitee_request(
        token_header=token_header,
        payload=payload,
        secret=secret,
        timestamp_header=timestamp_header,
    ):
        raise HTTPException(403, "Forbidden")

    event = request.headers.get("X-Gitee-Event", "") or request.headers.get("x-gitee-event", "")
    repo_name = _repo_from_payload(payload)
    if repo_name and not _repo_allowed(repo_name):
        logger.debug("gitee webhook ignored repo=%s", repo_name)
        return {"ok": True, "ignored": True}

    hook = str(payload.get("hook_name") or "")
    if hook == "push_hooks" or "push" in event.lower():
        shas = extract_push_shas(payload)
        if should_skip_gitee_push(shas):
            logger.debug("gitee push deduped shas=%s", shas[:1])
            return {"ok": True, "ignored": True, "deduped": True}
        record_push_shas(shas, source="gitee")

    summary = format_gitee_event(event, payload)
    if not summary:
        return {"ok": True, "ignored": True}

    try:
        from gitee_webhook.activity import classify_gitee_event
        from telegram_notify import notify_gitee_event
        from webhook_activity_buffer import record_webhook_event

        kind, repo = classify_gitee_event(event, payload)
        record_webhook_event(source="gitee", kind=kind, repo=repo)
        notify_gitee_event(summary)
    except Exception as exc:
        logger.exception("gitee webhook telegram notify failed event=%s", event)

    return {"ok": True, "event": event or hook}
