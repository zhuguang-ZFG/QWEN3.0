"""Internal direct-backend eval call (P2-25). Used via FRP from VPS for local proxies."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_guard import require_private_api_key
from backends_registry import BACKENDS
from eval_pinned_call import call_pinned_backend

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
    """Pinned backend eval — eval_pinned_call → routing_executor (no classify/select)."""
    name = body.backend.strip()
    cfg = BACKENDS.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"unknown backend: {name}")
    if not cfg.get("key"):
        raise HTTPException(status_code=404, detail=f"backend not configured: {name}")

    messages = [m.model_dump() for m in body.messages]
    try:
        final_backend, answer = await asyncio.to_thread(
            call_pinned_backend, name, messages, body.max_tokens,
        )
    except Exception as exc:
        _log.warning(
            "eval internal call failed backend=%s err=%s",
            name, type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"{type(exc).__name__}: {str(exc)[:200]}",
        ) from exc

    if final_backend == "exhausted" or not answer.strip():
        _log.warning("eval internal call exhausted backend=%s", name)
        raise HTTPException(status_code=502, detail=f"backend exhausted: {name}")

    return {"ok": True, "backend": final_backend, "answer": answer}
