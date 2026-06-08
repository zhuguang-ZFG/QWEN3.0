"""Jina Embedding API proxy for semantic search and RAG.

NOTE: api.jina.ai is not reachable from the current VPS (Alibaba Cloud).
This module works locally and on networks with unrestricted outbound access.
"""

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()
_log = logging.getLogger(__name__)

_JINA_BASE = "https://api.jina.ai/v1"
_JINA_KEY = os.environ.get(
    "JINA_API_KEY",
    "jina_cc30f9e51d22462b888f36db3196d6db-ASKWFSodA8p2ChSmOKmggQINTNP",
)
_JINA_TIMEOUT = 30.0


async def _jina_post(path: str, body: dict) -> dict:
    """Forward a POST request to Jina AI."""
    if not _JINA_KEY:
        raise HTTPException(status_code=503, detail="JINA_API_KEY is not configured")
    url = f"{_JINA_BASE}{path}"
    async with httpx.AsyncClient(timeout=_JINA_TIMEOUT) as client:
        resp = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {_JINA_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


@router.post("/v1/embeddings/jina")
async def jina_embeddings(request: Request):
    """Generate embeddings via Jina AI (OpenAI-compatible).

    Body fields:
      - input (list[str]): texts to embed
      - model (str): default "jina-embeddings-v3"
      - dimensions (int): default 1024
    """
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("jina embeddings invalid JSON: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    input_texts = body.get("input", [])
    if not input_texts:
        raise HTTPException(status_code=400, detail="input is required (list of texts)")

    payload = {
        "model": body.get("model", "jina-embeddings-v3"),
        "input": input_texts,
        "dimensions": body.get("dimensions", 1024),
    }

    try:
        result = await _jina_post("/embeddings", payload)
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("jina embedding HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Jina AI upstream error {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        _log.warning("jina embedding network error: %s %s", type(exc).__name__, repr(exc))
        raise HTTPException(status_code=502, detail="Network error reaching Jina AI")


@router.post("/v1/rerank/jina")
async def jina_rerank(request: Request):
    """Rerank documents by relevance to a query via Jina AI.

    Body fields:
      - query (str): the search query
      - documents (list[str]): documents to rerank
      - model (str): default "jina-reranker-v2-base-multilingual"
      - top_n (int): optional, return top N results
    """
    try:
        body = await request.json()
    except Exception as exc:
        _log.warning("jina rerank invalid JSON: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    query = body.get("query", "").strip()
    documents = body.get("documents", [])
    if not query or not documents:
        raise HTTPException(status_code=400, detail="query and documents are required")

    payload = {
        "model": body.get("model", "jina-reranker-v2-base-multilingual"),
        "query": query,
        "documents": documents,
    }
    if body.get("top_n"):
        payload["top_n"] = body["top_n"]

    try:
        result = await _jina_post("/rerank", payload)
        return JSONResponse(result)
    except httpx.HTTPStatusError as exc:
        _log.warning("jina rerank HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Jina AI upstream error {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        _log.warning("jina rerank network error: %s", type(exc).__name__, repr(exc))
        raise HTTPException(status_code=502, detail="Network error reaching Jina AI")
