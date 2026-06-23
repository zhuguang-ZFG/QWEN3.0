"""routes/embeddings.py — OpenAI-compatible embeddings proxy (Jina AI)."""

import json

from fastapi import APIRouter, Depends, Request

from config.env import gfw_proxy, jina_api_key
from fastapi.responses import JSONResponse
import httpx

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter()
MAX_EMBEDDING_INPUTS = 64
MAX_EMBEDDING_DIMENSIONS = 4096


def _normalize_input(value) -> list[str] | JSONResponse:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = value
    else:
        return JSONResponse({"error": "input must be a string or list of strings"}, status_code=400)
    if not items:
        return JSONResponse({"error": "input must not be empty"}, status_code=400)
    if len(items) > MAX_EMBEDDING_INPUTS:
        return JSONResponse({"error": f"input supports at most {MAX_EMBEDDING_INPUTS} items"}, status_code=400)
    return items


def _normalize_dimensions(value) -> int | JSONResponse:
    if not isinstance(value, int) or isinstance(value, bool):
        return JSONResponse({"error": "dimensions must be an integer"}, status_code=400)
    if value < 1 or value > MAX_EMBEDDING_DIMENSIONS:
        return JSONResponse({"error": f"dimensions must be between 1 and {MAX_EMBEDDING_DIMENSIONS}"}, status_code=400)
    return value


@router.post("/v1/embeddings", dependencies=[Depends(require_private_api_key)])
async def embeddings(request: Request):
    """OpenAI-compatible embeddings endpoint, proxied to Jina AI."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    inp = _normalize_input(body.get("input", []))
    if isinstance(inp, JSONResponse):
        return inp
    model = body.get("model", "jina-embeddings-v3")
    dimensions = _normalize_dimensions(body.get("dimensions", 256))
    if isinstance(dimensions, JSONResponse):
        return dimensions

    key = jina_api_key()
    if not key:
        return JSONResponse({"error": "JINA_API_KEY not configured"}, status_code=503)

    proxy = gfw_proxy()
    payload = {"model": model, "input": inp, "dimensions": dimensions}
    try:
        if proxy:
            client_ctx = httpx.AsyncClient(timeout=15.0, proxy=proxy)
        else:
            client_ctx = httpx.AsyncClient(timeout=15.0)
        async with client_ctx as client:
            resp = await client.post(
                "https://api.jina.ai/v1/embeddings",
                json=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "LiMa/1.3",
                },
            )
            resp.raise_for_status()
            return JSONResponse(resp.json())
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        return JSONResponse({"error": str(e)[:100]}, status_code=502)
