"""Internal direct-backend eval call (P2-25). Used via FRP from VPS for local proxies."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_guard import require_private_api_key
from backends import BACKENDS

_log = logging.getLogger(__name__)

router = APIRouter()


class EvalCallMessage(BaseModel):
    role: str
    content: str = ""


class EvalCallRequest(BaseModel):
    backend: str
    messages: list[EvalCallMessage]
    max_tokens: int = Field(default=512, ge=1, le=8192)


@router.post("/internal/v1/eval/call", dependencies=[Depends(require_private_api_key)])
async def eval_call_direct(body: EvalCallRequest) -> dict:
    """Direct http_caller for one backend — runs on the machine that owns local proxies."""
    name = body.backend.strip()
    cfg = BACKENDS.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"unknown backend: {name}")
    if not cfg.get("key"):
        raise HTTPException(status_code=404, detail=f"backend not configured: {name}")

    import http_caller

    messages = [m.model_dump() for m in body.messages]
    try:
        answer = http_caller.call_api(name, messages, body.max_tokens)
    except Exception as exc:
        _log.warning("eval internal call failed backend=%s err=%s", name, type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail=f"{type(exc).__name__}: {str(exc)[:200]}",
        ) from exc

    return {"ok": True, "backend": name, "answer": answer}
