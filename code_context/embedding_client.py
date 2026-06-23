"""Embedding client for code_context semantic search via Jina AI."""

import json
import urllib.error
import urllib.request

from config.settings import EMBEDDING


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

    body = json.dumps(
        {
            "model": "jina-embeddings-v3",
            "input": texts,
            "dimensions": dimensions,
        }
    ).encode()

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "LiMa/1.3",
    }

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
        return [item["embedding"] for item in data.get("data", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        return []
