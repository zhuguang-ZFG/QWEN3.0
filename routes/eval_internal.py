"""Internal direct-backend eval call (P2-25). Used via FRP from VPS for local proxies.

DEPRECATED v3.0: Coding/eval capability retired. The endpoint now returns 410 Gone
to indicate the capability is no longer available.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_guard import require_private_api_key

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
    """Pinned backend eval — retired in v3.0, returns 410 Gone."""
    _log.debug("/internal/v1/eval/call called but eval capability is retired")
    raise HTTPException(
        status_code=410,
        detail="eval capability retired in v3.0",
    )
