"""Ops eval-gate endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter()


@router.get("/eval/revision", dependencies=[Depends(require_private_api_key)])
async def ops_eval_revision() -> JSONResponse:
    """Return all eval candidates with promotion status."""
    try:
        from session_memory.eval_gate import revision_check

        return JSONResponse(revision_check())
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)


@router.post("/eval/approve", dependencies=[Depends(require_private_api_key)])
async def ops_eval_approve(request: Request) -> JSONResponse:
    """Manually approve a pattern candidate. Body: {pattern_key, rollback_notes}."""
    try:
        body = await read_json_object(request)
        if isinstance(body, JSONResponse):
            return body
        pattern_key = body.get("pattern_key", "")
        rollback = body.get("rollback_notes", "")
        if not pattern_key:
            return JSONResponse({"error": "pattern_key required"}, status_code=400)
        from session_memory.eval_gate import approve_candidate

        return JSONResponse(approve_candidate(pattern_key, rollback))
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)


@router.post("/eval/apply", dependencies=[Depends(require_private_api_key)])
async def ops_eval_apply(request: Request) -> JSONResponse:
    """Apply an approved pattern to runtime routing weights. Body: {pattern_key}."""
    try:
        body = await read_json_object(request)
        if isinstance(body, JSONResponse):
            return body
        pattern_key = body.get("pattern_key", "")
        if not isinstance(pattern_key, str) or not pattern_key.strip():
            return JSONResponse({"error": "pattern_key required"}, status_code=400)
        from session_memory.eval_gate import apply_promotion

        return JSONResponse(apply_promotion(pattern_key))
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)
