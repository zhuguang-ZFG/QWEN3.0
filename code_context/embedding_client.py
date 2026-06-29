"""Embedding client for code_context semantic search via Jina AI."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import httpx

from config.settings import EMBEDDING


def _build_payload(texts: list[str], dimensions: int) -> bytes:
    return json.dumps(
        {
            "model": "jina-embeddings-v3",
            "input": texts,
            "dimensions": dimensions,
        }
    ).encode()


def _build_headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "LiMa/1.3",
    }


def _parse_embedding_response(data: Any) -> list[list[float]]:
    try:
        return [item["embedding"] for item in data.get("data", [])]
    except (TypeError, KeyError):
        return []


def get_embeddings(
    texts: list[str],
    *,
    dimensions: int = 256,
    api_url: str = "",
    api_key: str = "",
) -> list[list[float]]:
    """Get embeddings from Jina AI. Returns empty list on failure."""
    if not texts:
        return []

    url = api_url or EMBEDDING.url
    key = api_key or EMBEDDING.jina_api_key

    if not key:
        return []

    body = _build_payload(texts, dimensions)
    headers = _build_headers(key)

    gfw_proxy = EMBEDDING.gfw_proxy
    if gfw_proxy:
        handler = urllib.request.ProxyHandler({"https": gfw_proxy})
        opener = urllib.request.build_opener(handler)
    else:
        opener = urllib.request.build_opener()

    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        resp = opener.open(req, timeout=15)
        data = json.loads(resp.read())
        return _parse_embedding_response(data)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        return []


async def get_embeddings_async(
    texts: list[str],
    *,
    dimensions: int = 256,
    api_url: str = "",
    api_key: str = "",
) -> list[list[float]]:
    """Async variant of get_embeddings using httpx. Returns empty list on failure."""
    if not texts:
        return []

    url = api_url or EMBEDDING.url
    key = api_key or EMBEDDING.jina_api_key

    if not key:
        return []

    body = _build_payload(texts, dimensions)
    headers = _build_headers(key)
    proxy = EMBEDDING.gfw_proxy or None

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=15, headers=headers) as client:
            resp = await client.post(url, content=body)
            resp.raise_for_status()
            return _parse_embedding_response(resp.json())
    except (httpx.HTTPError, OSError, json.JSONDecodeError, TypeError):
        return []
