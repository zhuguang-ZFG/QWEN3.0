"""Gitee 模力方舟 AI adapter (GI-G-3)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from provider_automation.catalog import ModelAdmissionStatus, ProviderModelEntry, ProviderModelSnapshot

_log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = ROOT / "data" / "gitee_ai_inventory.json"
DEFAULT_BASE_URL = "https://ai.gitee.com/v1"
MAX_SMOKE_LATENCY_MS = 20_000
_SMOKE_PROMPT = "Say OK only."

_NON_CHAT_HINTS = (
    "vidu", "wan2", "flux", "embedding", "bge-", "tts", "speech", "whisper",
    "stable-diffusion", "image", "video", "ocr", "rerank",
)
_CHAT_HINTS = (
    "qwen", "deepseek", "glm", "llama", "mistral", "gemma", "instruct", "chat",
    "coder", "phi-", "nemotron", "kimi", "hermes", "gpt", "flash", "turbo",
)


def gitee_ai_enabled() -> bool:
    return os.environ.get("GITEE_AI_ENABLED", "0") == "1"


def credentials_configured() -> bool:
    return bool(os.environ.get("GITEE_AI_TOKEN", "").strip())


def base_url() -> str:
    return os.environ.get("GITEE_AI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def token() -> str:
    return os.environ.get("GITEE_AI_TOKEN", "").strip()


def model_slug(model_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", model_id).strip("_").lower()
    return slug[:48] or "model"


def backend_key_from_model(model_id: str) -> str:
    return f"gitee_{model_slug(model_id)}"


def is_chat_candidate(model_id: str) -> bool:
    text = model_id.lower()
    if any(h in text for h in _NON_CHAT_HINTS):
        return False
    return any(h in text for h in _CHAT_HINTS)


def classify_error_payload(payload: dict[str, Any]) -> str:
    err = payload.get("error") or {}
    message = str(err.get("message") or "")
    lower = message.lower()
    if "资源" in message or "resource" in lower or "授权" in message:
        return "resource_not_bound"
    if "免费" in message or "free api access limit" in lower:
        return "free_quota_exhausted"
    if err.get("code"):
        return f"api_{err.get('code')}"
    return "unknown"


def fetch_models(*, client: httpx.Client | None = None) -> dict[str, Any]:
    if not credentials_configured():
        raise RuntimeError("GITEE_AI_TOKEN required")
    owns = client is None
    if client is None:
        client = httpx.Client(timeout=45.0)
    try:
        response = client.get(
            f"{base_url()}/models",
            headers={"Authorization": f"Bearer {token()}"},
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns:
            client.close()
    models = []
    for item in payload.get("data") or []:
        if isinstance(item, dict) and item.get("id"):
            models.append({"model_id": str(item["id"]), "object": item.get("object", "model")})
    models.sort(key=lambda m: m["model_id"])
    return {
        "provider": "gitee",
        "fetched_at": time.time(),
        "model_count": len(models),
        "models": models,
    }


def load_inventory(path: str | Path = "") -> dict[str, Any]:
    inv_path = Path(path) if path else DEFAULT_INVENTORY
    if not inv_path.is_file():
        return {"provider": "gitee", "models": []}
    return json.loads(inv_path.read_text(encoding="utf-8"))


def inventory_item_to_entry(item: dict[str, Any]) -> ProviderModelEntry:
    model_id = str(item.get("model_id") or "")
    return ProviderModelEntry(
        model_id=model_id,
        provider="gitee",
        display_name=model_id,
        pricing="metered",
        capabilities=["chat"],
        endpoint_count=1,
        admission_status=ModelAdmissionStatus.UNKNOWN,
        source_evidence="gitee_ai_inventory",
    )


def parse_inventory(path: str | Path = "") -> ProviderModelSnapshot:
    payload = load_inventory(path)
    models = []
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "")
        if is_chat_candidate(model_id):
            models.append(inventory_item_to_entry(item))
    models.sort(key=lambda m: m.model_id)
    return ProviderModelSnapshot(
        provider="gitee",
        source=str(path or DEFAULT_INVENTORY),
        fetched_at=float(payload.get("fetched_at") or time.time()),
        models=models,
    )


def build_backend_config(model_id: str) -> dict[str, str | int]:
    return {
        "url": f"{base_url()}/chat/completions",
        "key": token(),
        "model": model_id,
        "fmt": "openai",
        "timeout": 45,
        "admission": "chat_floor_only",
    }


def call_gitee_chat(
    model_id: str,
    messages: list[dict[str, str]],
    max_tokens: int = 64,
    *,
    client: httpx.Client | None = None,
) -> tuple[str, float]:
    if not credentials_configured():
        raise RuntimeError("GITEE_AI_TOKEN required")
    owns = client is None
    if client is None:
        client = httpx.Client(timeout=45.0)
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    t0 = time.time()
    try:
        response = client.post(f"{base_url()}/chat/completions", headers=headers, json=body)
        latency_ms = (time.time() - t0) * 1000
        if response.status_code >= 400:
            try:
                reason = classify_error_payload(response.json())
            except Exception as exc:
                _log.warning("operation failed: %s", exc)
                reason = f"http_{response.status_code}"
            raise RuntimeError(f"{reason}: {response.text[:200]}")
        payload = response.json()
    finally:
        if owns:
            client.close()
    if latency_ms > MAX_SMOKE_LATENCY_MS:
        raise RuntimeError(f"latency {latency_ms:.0f}ms exceeds cap")
    choices = payload.get("choices") or []
    text = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        text = str(message.get("content") or "")
    return text, latency_ms


def probe_model(model_id: str) -> dict[str, Any]:
    """Smoke one model; returns status dict for probe reports."""
    try:
        text, latency_ms = call_gitee_chat(
            model_id, [{"role": "user", "content": _SMOKE_PROMPT}], 8,
        )
        ok = bool(text.strip())
        return {
            "model_id": model_id,
            "backend_key": backend_key_from_model(model_id),
            "ok": ok,
            "latency_ms": round(latency_ms, 1),
            "preview": text[:80],
        }
    except Exception as exc:
        msg = str(exc)
        reason = "resource_not_bound" if "resource_not_bound" in msg else type(exc).__name__
        return {
            "model_id": model_id,
            "backend_key": backend_key_from_model(model_id),
            "ok": False,
            "reason": reason,
            "error": msg[:240],
        }
