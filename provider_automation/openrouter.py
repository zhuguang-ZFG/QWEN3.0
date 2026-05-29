"""OpenRouter catalog parser.

Default behavior is fixture-only. Live API fetch requires an explicit runtime
environment gate: LIMA_OPENROUTER_LIVE_FETCH=1.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProviderModelEntry,
    ProviderModelSnapshot,
)


_WATCHLIST_PATTERNS: dict[str, str] = {
    "elephant": "unverified model; endpoint_count and source evidence required",
    "alpha": "generic or experimental model name; verify current endpoints",
    "stealth": "opaque architecture; safety review needed",
}

_DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent / "data" / "openrouter_fixture.json"
)


@dataclass
class OpenRouterModel:
    id: str
    name: str = ""
    context_length: int = 0
    pricing: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    architecture: dict[str, Any] = field(default_factory=dict)
    endpoint_count: int = 0

    def to_entry(self) -> ProviderModelEntry:
        watchlist_reason = self._watchlist_reason()
        admission_status = (
            ModelAdmissionStatus.WATCHLIST
            if watchlist_reason or self.endpoint_count <= 0
            else ModelAdmissionStatus.UNKNOWN
        )
        privacy_note = watchlist_reason
        if self.endpoint_count <= 0:
            privacy_note = _join_notes(privacy_note, "no known endpoints")

        return ProviderModelEntry(
            model_id=self.id,
            provider="openrouter",
            display_name=self.name,
            context_window=max(0, int(self.context_length or 0)),
            pricing=self._pricing_class(),
            privacy_note=privacy_note,
            capabilities=self._infer_capabilities(),
            endpoint_count=max(0, int(self.endpoint_count or 0)),
            admission_status=admission_status,
            evidence_refs=[f"openrouter_catalog:{int(time.time())}"],
            source_evidence="openrouter_api_models",
            raw_metadata={
                "description": self.description[:200],
                "architecture": self.architecture,
            },
        )

    def _pricing_class(self) -> str:
        prompt_price = _safe_float(self.pricing.get("prompt"))
        completion_price = _safe_float(self.pricing.get("completion"))
        if prompt_price == 0 and completion_price == 0:
            return "free"
        if prompt_price is None and completion_price is None:
            return "unknown"
        return "paid"

    def _watchlist_reason(self) -> str:
        model_text = f"{self.id} {self.name}".lower()
        for pattern, reason in _WATCHLIST_PATTERNS.items():
            if pattern in model_text:
                return reason
        return ""

    def _infer_capabilities(self) -> list[str]:
        capabilities = []
        desc = f"{self.description} {self.name}".lower()
        modality = str(self.architecture.get("modality", "")).lower()
        if any(word in desc for word in ("code", "coder", "programming")):
            capabilities.append("code")
        if any(word in desc for word in ("vision", "image", "multimodal")) or "image" in modality:
            capabilities.append("vision")
        if any(word in desc for word in ("tool", "function")):
            capabilities.append("tool_calls")
        if any(word in desc for word in ("reason", "think", "chain")):
            capabilities.append("deep_reasoning")
        if "json" in desc or "structured" in desc:
            capabilities.append("json_mode")
        return sorted(set(capabilities))


def parse_fixture(fixture_path: str = "") -> ProviderModelSnapshot:
    """Parse an OpenRouter model list from a local JSON fixture."""
    path = Path(fixture_path) if fixture_path else _DEFAULT_FIXTURE
    if not path.exists():
        return ProviderModelSnapshot(
            provider="openrouter",
            source="fixture",
            fetched_at=time.time(),
            models=[],
        )

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    models_data = data if isinstance(data, list) else data.get("data", [])
    entries = [_parse_model_item(item) for item in models_data if isinstance(item, dict)]
    entries = [entry for entry in entries if entry is not None]

    return ProviderModelSnapshot(
        provider="openrouter",
        source="fixture",
        fetched_at=time.time(),
        models=entries,
    )


async def fetch_live() -> ProviderModelSnapshot:
    """Fetch OpenRouter model metadata when the runtime gate is enabled."""
    if not _live_fetch_enabled():
        raise RuntimeError(
            "Live OpenRouter fetch requires LIMA_OPENROUTER_LIVE_FETCH=1. "
            "Use parse_fixture() for offline testing."
        )

    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        data = response.json()

    models_data = data.get("data", [])
    entries = [_parse_model_item(item) for item in models_data if isinstance(item, dict)]
    entries = [entry for entry in entries if entry is not None]
    return ProviderModelSnapshot(
        provider="openrouter",
        source="openrouter_api",
        fetched_at=time.time(),
        models=entries,
    )


def create_empty_fixture(output_path: str = "") -> str:
    """Create a minimal OpenRouter fixture for offline testing."""
    path = Path(output_path) if output_path else _DEFAULT_FIXTURE
    fixture = {
        "data": [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "context_length": 128000,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "OpenAI GPT-4o multimodal model",
                "architecture": {"modality": "text+image"},
                "endpoint_count": 1,
            },
            {
                "id": "qwen/qwen3-coder",
                "name": "Qwen3 Coder",
                "context_length": 32768,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "Qwen code generation model with JSON support",
                "architecture": {"modality": "text"},
                "endpoint_count": 1,
            },
            {
                "id": "elephant/alpha-experimental",
                "name": "Elephant Alpha",
                "context_length": 8192,
                "pricing": {"prompt": "0", "completion": "0"},
                "description": "Experimental model with limited documentation",
                "architecture": {},
                "endpoint_count": 0,
            },
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(fixture, handle, indent=2)
    return str(path)


def _parse_model_item(item: dict[str, Any]) -> ProviderModelEntry | None:
    model_id = str(item.get("id", "")).strip()
    if not model_id:
        return None
    try:
        context_length = int(item.get("context_length", 0) or 0)
    except (TypeError, ValueError):
        context_length = 0
    return OpenRouterModel(
        id=model_id,
        name=str(item.get("name", "") or ""),
        context_length=context_length,
        pricing=item.get("pricing", {}) if isinstance(item.get("pricing"), dict) else {},
        description=str(item.get("description", "") or ""),
        architecture=(
            item.get("architecture", {}) if isinstance(item.get("architecture"), dict) else {}
        ),
        endpoint_count=_extract_endpoint_count(item),
    ).to_entry()


def _extract_endpoint_count(item: dict[str, Any]) -> int:
    if "endpoint_count" in item:
        try:
            return int(item.get("endpoint_count") or 0)
        except (TypeError, ValueError):
            return 0
    endpoints = item.get("endpoints")
    if isinstance(endpoints, list):
        return len(endpoints)
    return 0


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _live_fetch_enabled() -> bool:
    return os.environ.get("LIMA_OPENROUTER_LIVE_FETCH", "") == "1"


def _join_notes(left: str, right: str) -> str:
    if left and right:
        return f"{left}; {right}"
    return left or right
