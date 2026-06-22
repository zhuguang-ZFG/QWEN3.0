"""Provider model catalog snapshot and delta tracking.

Catalog discovery is only evidence. A model appearing in a provider catalog is
never enough to make it routeable; routing requires probes, quality checks, and
manual admission.
"""

from __future__ import annotations
from common.type_helpers import _safe_int

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_REDACTED = "[REDACTED]"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)


class ModelAdmissionStatus(str, Enum):
    UNKNOWN = "unknown"
    REJECTED = "rejected"
    WATCHLIST = "watchlist"
    SANDBOX_ONLY = "sandbox_only"
    CANDIDATE = "candidate"
    ROUTING_ENABLED = "routing_enabled"


class ProbeLevel(str, Enum):
    METADATA_ONLY = "metadata_only"
    COMPLETION_SMOKE = "completion_smoke"
    STREAM_SMOKE = "stream_smoke"
    CODING_FIXTURE = "coding_fixture"
    QUALITY_GATE = "quality_gate"


@dataclass
class ProviderModelEntry:
    model_id: str
    provider: str
    display_name: str = ""
    context_window: int = 0
    pricing: str = "unknown"
    privacy_note: str = ""
    capabilities: list[str] = field(default_factory=list)
    endpoint_count: int = 0
    admission_status: ModelAdmissionStatus = ModelAdmissionStatus.UNKNOWN
    highest_probe_level: ProbeLevel = ProbeLevel.METADATA_ONLY
    evidence_refs: list[str] = field(default_factory=list)
    source_evidence: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    @property
    def is_routeable(self) -> bool:
        return self.admission_status is ModelAdmissionStatus.ROUTING_ENABLED

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "display_name": self.display_name,
            "context_window": self.context_window,
            "pricing": self.pricing,
            "privacy_note": _redact_text(self.privacy_note),
            "capabilities": list(self.capabilities),
            "endpoint_count": self.endpoint_count,
            "admission_status": self.admission_status.value,
            "highest_probe_level": self.highest_probe_level.value,
            "evidence_refs": [_redact_text(ref) for ref in self.evidence_refs],
            "source_evidence": _redact_text(self.source_evidence),
            "raw_metadata": _redact_value(self.raw_metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderModelEntry":
        return cls(
            model_id=str(data.get("model_id", "")),
            provider=str(data.get("provider", "")),
            display_name=str(data.get("display_name", "")),
            context_window=_safe_int(data.get("context_window", 0)),
            pricing=str(data.get("pricing", "unknown")),
            privacy_note=str(data.get("privacy_note", "")),
            capabilities=_string_list(data.get("capabilities")),
            endpoint_count=_safe_int(data.get("endpoint_count", 0)),
            admission_status=_parse_enum(
                ModelAdmissionStatus,
                data.get("admission_status"),
                ModelAdmissionStatus.UNKNOWN,
            ),
            highest_probe_level=_parse_enum(
                ProbeLevel,
                data.get("highest_probe_level"),
                ProbeLevel.METADATA_ONLY,
            ),
            evidence_refs=_string_list(data.get("evidence_refs")),
            source_evidence=str(data.get("source_evidence", "")),
            raw_metadata=_dict_or_empty(data.get("raw_metadata")),
        )


@dataclass
class ProviderModelSnapshot:
    provider: str
    source: str
    fetched_at: float = 0.0
    models: list[ProviderModelEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        for model in self.models:
            if model.provider != self.provider:
                raise ValueError("snapshot contains model from a different provider")

    def model_ids(self) -> set[str]:
        return {model.model_id for model in self.models}

    def get(self, model_id: str) -> ProviderModelEntry | None:
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "models": [model.to_dict() for model in self.models],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderModelSnapshot":
        provider = str(data.get("provider", ""))
        return cls(
            provider=provider,
            source=str(data.get("source", "")),
            fetched_at=float(data.get("fetched_at", 0.0) or 0.0),
            models=[ProviderModelEntry.from_dict(item) for item in data.get("models", []) if isinstance(item, dict)],
        )


@dataclass
class ProviderCatalogDelta:
    provider: str
    old_snapshot: ProviderModelSnapshot
    new_snapshot: ProviderModelSnapshot
    added: list[ProviderModelEntry] = field(default_factory=list)
    removed: list[ProviderModelEntry] = field(default_factory=list)
    changed: list[tuple[ProviderModelEntry, ProviderModelEntry]] = field(default_factory=list)
    unchanged: list[ProviderModelEntry] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        lines = [
            f"Provider: {self.provider}",
            f"  Added:    {len(self.added)} models",
            f"  Removed:  {len(self.removed)} models",
            f"  Changed:  {len(self.changed)} models",
            f"  Unchanged:{len(self.unchanged)} models",
        ]
        if self.added:
            lines.append("  New models:")
            for model in self.added:
                lines.append(f"    + {model.model_id} ({model.pricing}, {model.context_window} ctx)")
        if self.removed:
            lines.append("  Removed models:")
            for model in self.removed:
                lines.append(f"    - {model.model_id}")
        return "\n".join(lines)


def compute_delta(
    old: ProviderModelSnapshot,
    new: ProviderModelSnapshot,
) -> ProviderCatalogDelta:
    """Compute the difference between two snapshots for the same provider."""
    if old.provider != new.provider:
        raise ValueError("cannot compute catalog delta across different providers")

    old_ids = old.model_ids()
    new_ids = new.model_ids()
    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    common_ids = sorted(old_ids & new_ids)

    added = [model for model_id in added_ids if (model := new.get(model_id))]
    removed = [model for model_id in removed_ids if (model := old.get(model_id))]
    changed: list[tuple[ProviderModelEntry, ProviderModelEntry]] = []
    unchanged: list[ProviderModelEntry] = []

    for model_id in common_ids:
        old_model = old.get(model_id)
        new_model = new.get(model_id)
        if old_model and new_model:
            if _model_changed(old_model, new_model):
                changed.append((old_model, new_model))
            else:
                unchanged.append(new_model)

    return ProviderCatalogDelta(
        provider=old.provider,
        old_snapshot=old,
        new_snapshot=new,
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
    )


def _model_changed(old: ProviderModelEntry, new: ProviderModelEntry) -> bool:
    return (
        old.pricing != new.pricing
        or old.context_window != new.context_window
        or old.privacy_note != new.privacy_note
        or sorted(old.capabilities) != sorted(new.capabilities)
        or old.endpoint_count != new.endpoint_count
        or old.admission_status != new.admission_status
        or old.highest_probe_level != new.highest_probe_level
    )


def _parse_enum(enum_type: type[Enum], value: Any, fallback: Any) -> Any:
    try:
        return enum_type(str(value))
    except ValueError:
        return fallback


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key)
            if _looks_secret(key_text):
                redacted[key_text] = _REDACTED
            else:
                redacted[key_text] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    text = str(value)
    lowered = text.lower()
    if any(marker in lowered for marker in ("sk-", "bearer ", "api_key=", "token=")):
        return _REDACTED
    return text


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def redact_provider_text(value: str) -> str:
    """Redact provider text before it appears in reports or patch plans."""
    return _redact_text(value)


def redact_provider_value(value: Any) -> Any:
    """Redact provider metadata before external serialization."""
    return _redact_value(value)
