"""Human-readable provider catalog change reports."""

from __future__ import annotations

from dataclasses import dataclass, field

from provider_automation.catalog import (
    ProviderCatalogDelta,
    ProviderModelEntry,
    redact_provider_text,
)


@dataclass
class ChangeReport:
    provider: str
    new_free_models: list[ProviderModelEntry] = field(default_factory=list)
    removed_models: list[ProviderModelEntry] = field(default_factory=list)
    capability_changes: list[tuple[ProviderModelEntry, ProviderModelEntry]] = field(
        default_factory=list
    )
    pricing_or_policy_changes: list[tuple[ProviderModelEntry, ProviderModelEntry]] = field(
        default_factory=list
    )
    routing_impacted: list[ProviderModelEntry] = field(default_factory=list)
    needs_review: list[ProviderModelEntry] = field(default_factory=list)
    watchlist_models: list[ProviderModelEntry] = field(default_factory=list)


def build_change_report(
    delta: ProviderCatalogDelta,
    currently_routed: set[str] | None = None,
) -> ChangeReport:
    """Build a structured report from a catalog delta."""
    currently_routed = currently_routed or set()

    new_free = [model for model in delta.added if model.pricing == "free"]
    removed = list(delta.removed)
    capability_changes = [
        (old, new)
        for old, new in delta.changed
        if sorted(old.capabilities) != sorted(new.capabilities)
    ]
    pricing_or_policy_changes = [
        (old, new)
        for old, new in delta.changed
        if (
            old.pricing != new.pricing
            or old.privacy_note != new.privacy_note
            or old.endpoint_count != new.endpoint_count
        )
    ]
    routing_impacted = [
        model for model in delta.removed if model.key() in currently_routed or model.model_id in currently_routed
    ]
    watchlist_models = [model for model in delta.added if model.privacy_note]
    needs_review = [model for model in new_free if model not in watchlist_models]

    return ChangeReport(
        provider=delta.provider,
        new_free_models=new_free,
        removed_models=removed,
        capability_changes=capability_changes,
        pricing_or_policy_changes=pricing_or_policy_changes,
        routing_impacted=routing_impacted,
        needs_review=needs_review,
        watchlist_models=watchlist_models,
    )


def _format_routing_section(report: ChangeReport) -> list[str]:
    if not report.routing_impacted:
        return []
    lines = ["### ROUTING IMPACTED (urgent)"]
    for model in report.routing_impacted:
        lines.append(f"  - {redact_provider_text(model.model_id)}: removed from provider catalog but still in routing")
    return lines + [""]


def _format_new_free_section(report: ChangeReport) -> list[str]:
    if not report.new_free_models:
        return []
    lines = ["### New Free Models"]
    for model in report.new_free_models:
        caps = ", ".join(model.capabilities) if model.capabilities else "none"
        watch = " [WATCHLIST]" if model.privacy_note else ""
        lines.append(f"  + {redact_provider_text(model.model_id)} (ctx={model.context_window}, caps={redact_provider_text(caps)}){watch}")
    return lines + [""]


def _format_removed_section(report: ChangeReport) -> list[str]:
    if not report.removed_models:
        return []
    lines = ["### Removed Models"]
    for model in report.removed_models:
        lines.append(f"  - {redact_provider_text(model.model_id)}")
    return lines + [""]


def _format_capability_section(report: ChangeReport) -> list[str]:
    if not report.capability_changes:
        return []
    lines = ["### Capability Changes"]
    for old, new in report.capability_changes:
        added = ", ".join(sorted(set(new.capabilities) - set(old.capabilities)))
        removed = ", ".join(sorted(set(old.capabilities) - set(new.capabilities)))
        lines.append(f"  ~ {redact_provider_text(old.model_id)}:")
        if added:
            lines.append(f"      +added: {redact_provider_text(added)}")
        if removed:
            lines.append(f"      -removed: {redact_provider_text(removed)}")
    return lines + [""]


def _format_pricing_section(report: ChangeReport) -> list[str]:
    if not report.pricing_or_policy_changes:
        return []
    lines = ["### Pricing/Policy/Endpoint Changes"]
    for old, new in report.pricing_or_policy_changes:
        lines.append(f"  ~ {redact_provider_text(old.model_id)}: pricing {old.pricing}->{new.pricing}, endpoints {old.endpoint_count}->{new.endpoint_count}")
    return lines + [""]


def _format_watchlist_section(report: ChangeReport) -> list[str]:
    if not report.watchlist_models:
        return []
    lines = ["### Watchlist (requires evidence)"]
    for model in report.watchlist_models:
        lines.append(f"  ? {redact_provider_text(model.model_id)}: {redact_provider_text(model.privacy_note)}")
    return lines + [""]


def _format_review_section(report: ChangeReport) -> list[str]:
    if not report.needs_review:
        return []
    lines = ["### Needs Manual Review"]
    for model in report.needs_review:
        lines.append(f"  * {redact_provider_text(model.model_id)}")
    return lines + [""]


def format_change_report(report: ChangeReport) -> str:
    """Format a change report as safe markdown."""
    header = [f"## Provider Change Report: {redact_provider_text(report.provider)}", ""]
    sections = [
        *_format_routing_section(report),
        *_format_new_free_section(report),
        *_format_removed_section(report),
        *_format_capability_section(report),
        *_format_pricing_section(report),
        *_format_watchlist_section(report),
        *_format_review_section(report),
    ]
    if not sections:
        sections = ["No changes detected."]
    return "\n".join(header + sections)
