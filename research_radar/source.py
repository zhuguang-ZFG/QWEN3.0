"""Structured metadata for external research references.

Each source is a project, paper, tool, or article that informed LiMa's
architecture. Records track provenance, license status, adoption state, and
evidence links so the research trail stays auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_REDACTED = "[REDACTED]"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "cookie",
    "credential",
    "password",
    "secret",
    "sk-",
    "token=",
)


class AdoptionState(str, Enum):
    CONCEPT_ONLY = "concept_only"
    REFERENCE = "reference"
    EVALUATING = "evaluating"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class LicenseClass(str, Enum):
    MIT = "MIT"
    APACHE2 = "Apache-2.0"
    BSD = "BSD"
    GPL = "GPL"
    LGPL = "LGPL"
    AGPL = "AGPL"
    MPL = "MPL-2.0"
    CC_BY_NC_SA = "CC BY-NC-SA"
    UNLICENSE = "Unlicense"
    SOURCE_AVAILABLE = "source-available"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"
    NO_LICENSE = "no-license"


_COPY_RESTRICTED_LICENSES = {
    LicenseClass.AGPL,
    LicenseClass.GPL,
    LicenseClass.LGPL,
    LicenseClass.NO_LICENSE,
    LicenseClass.PROPRIETARY,
    LicenseClass.SOURCE_AVAILABLE,
    LicenseClass.UNKNOWN,
}


@dataclass
class SourceRecord:
    source_id: str
    name: str
    url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    license_class: LicenseClass = LicenseClass.UNKNOWN
    adoption_state: AdoptionState = AdoptionState.REFERENCE
    subsystem: str = ""
    notes: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    added_at: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        if not self.name:
            raise ValueError("name is required")
        self.tags = _string_list(self.tags)
        self.evidence_refs = _string_list(self.evidence_refs)

    @property
    def allows_code_copy(self) -> bool:
        return self.license_class not in _COPY_RESTRICTED_LICENSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": redact_research_text(self.source_id),
            "name": redact_research_text(self.name),
            "url": redact_research_text(self.url),
            "description": redact_research_text(self.description),
            "tags": [redact_research_text(tag) for tag in self.tags],
            "license_class": self.license_class.value,
            "adoption_state": self.adoption_state.value,
            "subsystem": redact_research_text(self.subsystem),
            "notes": redact_research_text(self.notes),
            "evidence_refs": [
                redact_research_text(ref) for ref in self.evidence_refs
            ],
            "added_at": redact_research_text(self.added_at),
            "reviewed_at": redact_research_text(self.reviewed_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        return cls(
            source_id=str(data.get("source_id", "")),
            name=str(data.get("name", "")),
            url=str(data.get("url", "")),
            description=str(data.get("description", "")),
            tags=_string_list(data.get("tags")),
            license_class=_parse_enum(
                LicenseClass,
                data.get("license_class"),
                LicenseClass.UNKNOWN,
            ),
            adoption_state=_parse_enum(
                AdoptionState,
                data.get("adoption_state"),
                AdoptionState.REFERENCE,
            ),
            subsystem=str(data.get("subsystem", "")),
            notes=str(data.get("notes", "")),
            evidence_refs=_string_list(data.get("evidence_refs")),
            added_at=str(data.get("added_at", "")),
            reviewed_at=str(data.get("reviewed_at", "")),
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


def redact_research_text(value: str) -> str:
    text = str(value)
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return _REDACTED
    return text
