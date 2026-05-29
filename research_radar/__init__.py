"""Structured reference sources for LiMa architecture decisions."""

from research_radar.catalog import SourceCatalog, build_default_catalog
from research_radar.source import (
    AdoptionState,
    LicenseClass,
    SourceRecord,
    redact_research_text,
)

__all__ = [
    "AdoptionState",
    "LicenseClass",
    "SourceCatalog",
    "SourceRecord",
    "build_default_catalog",
    "redact_research_text",
]
