"""Proxy route for st.236600.xyz image generation API (gpt-image-2)."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()
_log = logging.getLogger(__name__)

_ST_BASE = "https://st.236600.xyz"
_ST_SPACE = "d6b95ae2adbc4725f0951b2b"
_TIMEOUT = 30.0


async def _proxy_get(path: str, params: dict | None = None) -> dict:
    """Proxy a GET request to st.236600.xyz."""
    url = f"{_ST_BASE}{path}"
    merged = dict(params or {})
    merged["space"] = _ST_SPACE
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=merged)
        resp.raise_for_status()
        return resp.json()


async def _proxy_post(path: str, body: dict) -> dict:
    """Proxy a POST request to st.236600.xyz."""
    url = f"{_ST_BASE}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            params={"space": _ST_SPACE},
            json=body,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


@router.post("/v1/images/st236600_generate")
async def st236600_generate(request: Request):
    """Submit an image generation task to st.236600.xyz."""
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("st236600 generate invalid JSON: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Ensure required fields (st.236600.xyz uses model_id, not model)
    body.setdefault("mode", "text2image")
    body.setdefault("model_id", "113")
    body.setdefault("size", "1024x1024")
    body.setdefault("n", 1)
    body.setdefault("output_format", "png")
    body.setdefault("source_images", [])
    body.setdefault("quality", "auto")

    try:
        result = await _proxy_post("/api/generate.php", body)
        if not result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=result.get("message", "st.236600.xyz generate failed"),
            )
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("st236600 generate HTTP error: %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"Upstream error {exc.response.status_code}")
    except httpx.RequestError as exc:
        _log.warning("st236600 generate network error: %s", exc)
        raise HTTPException(status_code=502, detail="Network error reaching st.236600.xyz")


@router.get("/v1/images/st236600_status")
async def st236600_status(record_id: str):
    """Poll image generation task status from st.236600.xyz."""
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id required")
    try:
        result = await _proxy_get("/api/status.php", {"id": record_id})
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("st236600 status HTTP error: %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"Upstream error {exc.response.status_code}")
    except httpx.RequestError as exc:
        _log.warning("st236600 status network error: %s", exc)
        raise HTTPException(status_code=502, detail="Network error reaching st.236600.xyz")


@router.get("/v1/images/st236600_models")
async def st236600_models(mode: str = "text2image"):
    """Get available models from st.236600.xyz."""
    try:
        result = await _proxy_get("/api/models.php", {"mode": mode})
        return JSONResponse(result)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        _log.warning("st236600 models error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch models")
