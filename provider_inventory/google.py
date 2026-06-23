"""Google Gemini / Gemma model inventory."""

from __future__ import annotations

import time
from typing import Any

import httpx

from config import backend_config, settings

GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _api_key() -> str:
    return backend_config.GOOGLE_AI_KEY.strip()


def _inventory_proxy() -> str:
    """Proxy for Google API (same env chain as MCP inventory / http_caller)."""
    return settings.EMBEDDING.google_inventory_proxy or settings.EMBEDDING.gfw_proxy


def _build_client(*, proxy: str | None = None) -> httpx.Client:
    resolved = _inventory_proxy() if proxy is None else proxy.strip()
    kwargs: dict[str, object] = {"timeout": 30.0}
    if resolved:
        kwargs["proxy"] = resolved
    return httpx.Client(**kwargs)


def credentials_configured() -> bool:
    return bool(_api_key())


def normalize_google_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_name = str(item.get("name") or "").strip()
    model_id = raw_name.removeprefix("models/")
    methods = item.get("supportedGenerationMethods") or []
    if isinstance(methods, str):
        methods = [methods]
    return {
        "model_id": model_id,
        "name": str(item.get("displayName") or model_id),
        "description": str(item.get("description") or "")[:240],
        "source": "google_generative_language_api",
        "methods": list(methods),
        "input_token_limit": item.get("inputTokenLimit"),
        "output_token_limit": item.get("outputTokenLimit"),
    }


def parse_google_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("models") or []
    models: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_google_item(item)
        if not normalized["model_id"]:
            continue
        methods = normalized.get("methods") or []
        if methods and "generateContent" not in methods:
            continue
        models.append(normalized)
    models.sort(key=lambda m: m["model_id"])
    return models


def fetch_google_models(
    *,
    api_key: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    api_key = api_key or _api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_AI_KEY is required for live inventory")

    owns_client = client is None
    if client is None:
        client = _build_client()
    models: list[dict[str, Any]] = []
    page_token = ""
    try:
        while True:
            params: dict[str, str] = {"key": api_key, "pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token
            response = client.get(GOOGLE_MODELS_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            models.extend(parse_google_response(payload))
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                break
    finally:
        if owns_client:
            client.close()

    dedup = {m["model_id"]: m for m in models}
    ordered = sorted(dedup.values(), key=lambda m: m["model_id"])
    return {
        "provider": "google",
        "fetched_at": time.time(),
        "model_count": len(ordered),
        "models": ordered,
    }
