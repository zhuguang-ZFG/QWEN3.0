"""Provider model automation package.

Discovery never mutates production routing. Route admission remains gated by
probe evidence, quality checks, and manual review.
"""

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderCatalogDelta,
    ProviderModelEntry,
    ProviderModelSnapshot,
    compute_delta,
    redact_provider_text,
    redact_provider_value,
)

__all__ = [
    "ModelAdmissionStatus",
    "ProbeLevel",
    "ProviderCatalogDelta",
    "ProviderModelEntry",
    "ProviderModelSnapshot",
    "compute_delta",
    "redact_provider_text",
    "redact_provider_value",
]
