"""Proxy route for Agnes AI image generation API (OpenAI-compatible)."""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()
_log = logging.getLogger(__name__)

_AGNES_BASE = "https://apihub.agnes-ai.com"
_AGNES_KEY = os.environ.get("AGNES_API_KEY", "")
_AGNES_TIMEOUT = 120.0


async def _agnes_post(path: str, body: dict) -> dict:
    """Forward a POST request to Agnes AI."""
    if not _AGNES_KEY:
        raise HTTPException(status_code=503, detail="AGNES_API_KEY is not configured")
    url = f"{_AGNES_BASE}{path}"
    async with httpx.AsyncClient(timeout=_AGNES_TIMEOUT) as client:
        resp = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {_AGNES_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


@router.post("/v1/images/agnes_generate")
async def agnes_generate(request: Request):
    """Generate an image via Agnes AI (synchronous, OpenAI-compatible).

    Body fields:
      - prompt (str): image description
      - model (str): default "agnes-image-2.1-flash"
      - n (int): number of images, default 1
      - size (str): default "1024x1024"
    """
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("agnes generate invalid JSON: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    payload = {
        "model": body.get("model", "agnes-image-2.1-flash"),
        "prompt": prompt,
        "n": body.get("n", 1),
        "size": body.get("size", "1024x1024"),
    }

    try:
        result = await _agnes_post("/v1/images/generations", payload)
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("agnes generate HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Agnes AI upstream error {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        _log.warning("agnes generate network error: %s", exc)
        raise HTTPException(status_code=502, detail="Network error reaching Agnes AI")
