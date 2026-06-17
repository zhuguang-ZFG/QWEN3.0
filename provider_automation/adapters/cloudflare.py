"""Cloudflare Workers AI catalog adapter (CF-G-2 / PA-B)."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from provider_automation.catalog import ModelAdmissionStatus, ProviderModelEntry, ProviderModelSnapshot
from provider_inventory.compare import registered_model_ids

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = ROOT / "data" / "cf_model_inventory.json"
MAX_SMOKE_LATENCY_MS = 15_000
_SMOKE_PROMPT = "Say OK only."

_NON_CHAT_HINTS = (
    "embedding",
    "bge-",
    "reranker",
    "flux",
    "stable-diffusion",
    "deepgram",
    "aura-",
    "whisper",
    "lucid-origin",
    "phoenix",
    "dreamshaper",
    "indictrans",
    "m2m100",
    "bart-large",
    "distilbert",
    "llava",
    "segment",
    "translation",
    "/leonardo/",
    "embedgemma",
    "melotts",
    "smart-turn",
    "resnet-50",
    "llama-guard",
)
_CHAT_HINTS = (
    "instruct",
    "chat",
    "coder",
    "qwq",
    "reason",
    "thinking",
    "-it",
    "gpt-oss",
    "nemotron",
    "gemma",
    "llama",
    "mistral",
    "deepseek",
    "glm",
    "kimi",
    "qwen",
    "phi-",
    "sqlcoder",
    "hermes",
    "granite",
    "sea-lion",
)
_PROBE_PREFIXES = ("@cf/", "@hf/")


def load_inventory(path: str | Path = "") -> dict[str, Any]:
    inv_path = Path(path) if path else DEFAULT_INVENTORY
    if not inv_path.is_file():
        return {"provider": "cloudflare", "models": []}
    return json.loads(inv_path.read_text(encoding="utf-8"))


def is_chat_candidate(model_id: str, description: str = "") -> bool:
    return _is_probe_candidate(model_id, description)


def _is_probe_candidate(model_id: str, description: str = "") -> bool:
    text = f"{model_id} {description}".lower()
    if not model_id.startswith(_PROBE_PREFIXES):
        return False
    if any(hint in text for hint in _NON_CHAT_HINTS):
        return False
    return any(hint in text for hint in _CHAT_HINTS)


def _admitted_overlay_model_ids(admission_path: str | Path = "") -> set[str]:
    try:
        from backend_admission_store import load_store, parse_overlays

        data = load_store(admission_path)
        return {o.model_id for o in parse_overlays(data) if o.model_id}
    except Exception:
        return set()


def infer_capabilities(model_id: str, description: str = "") -> list[str]:
    text = f"{model_id} {description}".lower()
    caps: list[str] = []
    if any(x in text for x in ("coder", "code", "sqlcoder")):
        caps.append("code")
    if any(x in text for x in ("vision", "multimodal", "image")):
        caps.append("vision")
    if any(x in text for x in ("reason", "qwq", "thinking", "r1")):
        caps.append("deep_reasoning")
    if "chat" in text or "instruct" in text:
        caps.append("chat")
    return sorted(set(caps)) or ["chat"]


def inventory_item_to_entry(item: dict[str, Any]) -> ProviderModelEntry:
    model_id = str(item.get("model_id") or "")
    description = str(item.get("description") or "")
    return ProviderModelEntry(
        model_id=model_id,
        provider="cloudflare",
        display_name=str(item.get("name") or model_id),
        pricing="free",
        capabilities=infer_capabilities(model_id, description),
        endpoint_count=1,
        admission_status=ModelAdmissionStatus.UNKNOWN,
        source_evidence="cf_model_inventory",
        raw_metadata={"description": description[:240]},
    )


def parse_inventory(path: str | Path = "") -> ProviderModelSnapshot:
    payload = load_inventory(path)
    models = []
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "")
        if not is_chat_candidate(model_id, str(item.get("description") or "")):
            continue
        models.append(inventory_item_to_entry(item))
    models.sort(key=lambda m: m.model_id)
    return ProviderModelSnapshot(
        provider="cloudflare",
        source=str(path or DEFAULT_INVENTORY),
        fetched_at=float(payload.get("fetched_at") or time.time()),
        models=models,
    )


def parse_probe_inventory(path: str | Path = "") -> ProviderModelSnapshot:
    payload = load_inventory(path)
    models = []
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "")
        if not _is_probe_candidate(model_id, str(item.get("description") or "")):
            continue
        models.append(inventory_item_to_entry(item))
    models.sort(key=lambda m: m.model_id)
    return ProviderModelSnapshot(
        provider="cloudflare",
        source=str(path or DEFAULT_INVENTORY),
        fetched_at=float(payload.get("fetched_at") or time.time()),
        models=models,
    )


def unregistered_chat_candidates(path: str | Path = "") -> list[ProviderModelEntry]:
    return unregistered_probe_candidates(path)


def unregistered_probe_candidates(
    path: str | Path = "",
    *,
    admission_path: str | Path = "",
) -> list[ProviderModelEntry]:
    registered = registered_model_ids(("cf_",))
    admitted = _admitted_overlay_model_ids(admission_path)
    snapshot = parse_probe_inventory(path)
    return [m for m in snapshot.models if m.model_id not in registered and m.model_id not in admitted]


def map_model_to_backend_key(model_id: str) -> str:
    slug = model_id.removeprefix("@cf/").removeprefix("@hf/")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_").lower()
    return f"cf_{slug[:48]}"


def build_backend_config(model_id: str) -> dict[str, str | int]:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_TOKEN", "")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    return {
        "url": url,
        "key": token,
        "model": model_id,
        "fmt": "openai",
        "timeout": 30,
    }


def cf_credentials_configured() -> bool:
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_TOKEN"))


def call_cf_chat(
    model_id: str,
    messages: list[dict[str, str]],
    max_tokens: int = 64,
    *,
    client: httpx.Client | None = None,
) -> tuple[str, float]:
    """Call Cloudflare chat completions; returns (text, latency_ms)."""
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_TOKEN", "")
    if not account_id or not token:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_TOKEN required")

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
    owns = client is None
    if client is None:
        client = httpx.Client(timeout=45.0)
    t0 = time.time()
    try:
        response = client.post(url, headers=headers, json=body)
        latency_ms = (time.time() - t0) * 1000
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns:
            client.close()

    if latency_ms > MAX_SMOKE_LATENCY_MS:
        raise RuntimeError(f"latency {latency_ms:.0f}ms exceeds {MAX_SMOKE_LATENCY_MS}ms cap")

    choices = payload.get("choices") or []
    text = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        text = str(message.get("content") or "")
    return text, latency_ms


def make_smoke_callable():
    def _smoke(entry: ProviderModelEntry, messages: list[dict[str, str]], max_tokens: int) -> str:
        msgs = messages or [{"role": "user", "content": _SMOKE_PROMPT}]
        text, _latency = call_cf_chat(entry.model_id, msgs, max_tokens)
        return text

    return _smoke


_CODING_CASES = (
    ("Write a Python function add(a, b) that returns the sum.", ("def add", "return")),
    ("Reply with only the number 42.", ("42",)),
    ("Complete: print('hello')", ("print", "hello")),
)


def run_coding_fixture(entry: ProviderModelEntry) -> tuple[int, int]:
    passed = 0
    for prompt, markers in _CODING_CASES:
        try:
            text, _ = call_cf_chat(entry.model_id, [{"role": "user", "content": prompt}], 128)
            lower = text.lower()
            if all(marker.lower() in lower for marker in markers):
                passed += 1
        except Exception:
            continue
    return passed, len(_CODING_CASES)


def make_coding_callable():
    return lambda entry, _cases: run_coding_fixture(entry)


def suggest_admission_tier(entry: ProviderModelEntry, batch_result) -> str:
    """Map probe evidence to router tier (medium/floor only)."""
    from provider_automation.catalog import ProbeLevel

    highest = batch_result.highest_level_passed
    if highest is ProbeLevel.CODING_FIXTURE and "code" in entry.capabilities:
        return "floor"
    if highest in (ProbeLevel.COMPLETION_SMOKE, ProbeLevel.STREAM_SMOKE):
        return "medium"
    return "late_fallback"
