"""GitHub webhook endpoint — push/PR/CI summaries to Telegram."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from github_webhook.format import format_github_event
from github_webhook.verify import verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github")


def _is_enabled() -> bool:
    return os.environ.get("GITHUB_WEBHOOK_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _get_secret() -> str:
    return os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()


def _allowed_repos() -> set[str]:
    raw = os.environ.get("GITHUB_WEBHOOK_REPOS", "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _repo_allowed(full_name: str) -> bool:
    allowlist = _allowed_repos()
    if not allowlist:
        return True
    return full_name.lower() in allowlist


@router.post("/webhook")
async def github_webhook(request: Request):
    if not _is_enabled():
        raise HTTPException(503, "GitHub webhook not enabled")
    secret = _get_secret()
    if not secret:
        raise HTTPException(503, "GITHUB_WEBHOOK_SECRET not configured")

    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_github_signature(body, signature, secret):
        raise HTTPException(403, "Forbidden")

    event = request.headers.get("x-github-event", "")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("github webhook invalid json event=%s", event)
        return {"ok": True, "ignored": True}

    repo_name = str(payload.get("repository", {}).get("full_name") or "")
    if repo_name and not _repo_allowed(repo_name):
        logger.debug("github webhook ignored repo=%s", repo_name)
        return {"ok": True, "ignored": True}

    summary = format_github_event(event, payload)
    if not summary:
        return {"ok": True, "ignored": True}

    if event == "push":
        try:
            from github_webhook.format import extract_github_push_shas
            from gitee_webhook.dedupe import record_push_shas

            record_push_shas(extract_github_push_shas(payload), source="github")
        except Exception:
            logger.debug("github push dedupe record skipped", exc_info=True)

    try:
        from telegram_notify import notify_github_event
        from github_webhook.activity import classify_github_event
        from webhook_activity_buffer import record_webhook_event

        kind, repo = classify_github_event(event, payload)
        record_webhook_event(source="github", kind=kind, repo=repo)
        notify_github_event(summary)
    except Exception:
        logger.exception("github webhook telegram notify failed event=%s", event)

    return {"ok": True, "event": event}
