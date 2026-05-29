"""Cloudflare Workers AI model inventory."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

CF_SEARCH_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search"
)


def _account_id() -> str:
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()


def _token() -> str:
    return os.environ.get("CLOUDFLARE_TOKEN", "").strip()


def credentials_configured() -> bool:
    return bool(_account_id() and _token())


def normalize_cloudflare_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_id = str(item.get("id") or "").strip()
    label = str(item.get("name") or item.get("label") or "").strip()
    # Account search API uses internal UUID in `id`; slug lives in `name`.
    if label.startswith("@cf/") or label.startswith("@hf/"):
        model_id = label
    else:
        model_id = raw_id or label
    task = item
    if isinstance(item.get("task"), dict):
        task = item["task"]
    elif isinstance(item.get("properties"), dict):
        task = item["properties"]
    return {
        "model_id": model_id,
        "name": label or model_id,
        "description": str(item.get("description") or "")[:240],
        "source": "cloudflare_account_api",
        "properties": {
            k: task.get(k)
            for k in ("context_window", "max_input_tokens", "max_output_tokens")
            if task.get(k) is not None
        },
    }


def parse_cloudflare_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload.get("success", True) and payload.get("errors"):
        raise RuntimeError(f"cloudflare api error: {payload.get('errors')}")
    result = payload.get("result")
    if isinstance(result, dict):
        items = result.get("models") or result.get("data") or []
    elif isinstance(result, list):
        items = result
    else:
        items = payload.get("models") or payload.get("data") or []
    models: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized = normalize_cloudflare_item(item)
            if normalized["model_id"]:
                models.append(normalized)
    models.sort(key=lambda m: m["model_id"])
    return models


def fetch_cloudflare_models(
    *,
    account_id: str = "",
    token: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch Workers AI models from the account search API."""
    account_id = account_id or _account_id()
    token = token or _token()
    if not account_id or not token:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_TOKEN are required for live inventory"
        )

    url = CF_SEARCH_URL.format(account_id=account_id)
    headers = {"Authorization": f"Bearer {token}"}
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)
    try:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()

    models = parse_cloudflare_response(payload)
    return {
        "provider": "cloudflare",
        "fetched_at": time.time(),
        "account_id": account_id,
        "model_count": len(models),
        "models": models,
    }
