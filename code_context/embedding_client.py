"""Embedding client for code_context semantic search via Jina AI."""

import json
import os
import urllib.error
import urllib.request


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

    url = api_url or os.environ.get("LIMA_EMBEDDINGS_URL", "https://api.jina.ai/v1/embeddings")
    key = api_key or os.environ.get("JINA_API_KEY", "")

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

    gfw_proxy = os.environ.get("GFW_PROXY", "")
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
