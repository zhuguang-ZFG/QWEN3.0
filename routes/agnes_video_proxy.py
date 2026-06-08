"""Proxy route for Agnes AI video generation API."""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()
_log = logging.getLogger(__name__)

_AGNES_BASE = "https://apihub.agnes-ai.com"
_AGNES_KEY = os.environ.get("AGNES_API_KEY", "")
_AGNES_TIMEOUT = 300.0  # Video generation takes longer


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


@router.post("/v1/videos/agnes_generate")
async def agnes_video_generate(request: Request):
    """Generate a video via Agnes AI.

    Body fields:
      - prompt (str): video description
      - model (str): default "agnes-video-v2.0"
      - image_url (str, optional): reference image URL
      - duration (int, optional): video duration in seconds, default 5
      - aspect_ratio (str, optional): default "16:9"
    """
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("agnes video generate invalid JSON: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    payload = {
        "model": body.get("model", "agnes-video-v2.0"),
        "prompt": prompt,
    }

    # Optional parameters
    if body.get("image_url"):
        payload["image_url"] = body["image_url"]
    if body.get("duration"):
        payload["duration"] = body["duration"]
    if body.get("aspect_ratio"):
        payload["aspect_ratio"] = body["aspect_ratio"]

    try:
        result = await _agnes_post("/v1/video/generations", payload)
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("agnes video generate HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Agnes AI upstream error {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        _log.warning("agnes video generate network error: %s", exc)
        raise HTTPException(status_code=502, detail="Network error reaching Agnes AI")


@router.get("/v1/videos/agnes_status/{task_id}")
async def agnes_video_status(task_id: str):
    """Check video generation task status."""
    try:
        result = await _agnes_post(f"/v1/video/generations/{task_id}", {})
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("agnes video status HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Agnes AI upstream error {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        _log.warning("agnes video status network error: %s", exc)
        raise HTTPException(status_code=502, detail="Network error reaching Agnes AI")
