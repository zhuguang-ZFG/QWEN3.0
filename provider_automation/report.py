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


def format_change_report(report: ChangeReport) -> str:
    """Format a change report as safe markdown."""
    lines = [f"## Provider Change Report: {redact_provider_text(report.provider)}", ""]

    if report.routing_impacted:
        lines.append("### ROUTING IMPACTED (urgent)")
        for model in report.routing_impacted:
            lines.append(
                f"  - {redact_provider_text(model.model_id)}: "
                "removed from provider catalog but still in routing"
            )
        lines.append("")

    if report.new_free_models:
        lines.append("### New Free Models")
        for model in report.new_free_models:
            caps = ", ".join(model.capabilities) if model.capabilities else "none"
            watch = " [WATCHLIST]" if model.privacy_note else ""
            lines.append(
                f"  + {redact_provider_text(model.model_id)} "
                f"(ctx={model.context_window}, caps={redact_provider_text(caps)}){watch}"
            )
        lines.append("")

    if report.removed_models:
        lines.append("### Removed Models")
        for model in report.removed_models:
            lines.append(f"  - {redact_provider_text(model.model_id)}")
        lines.append("")

    if report.capability_changes:
        lines.append("### Capability Changes")
        for old, new in report.capability_changes:
            old_caps = set(old.capabilities)
            new_caps = set(new.capabilities)
            added = ", ".join(sorted(new_caps - old_caps))
            removed = ", ".join(sorted(old_caps - new_caps))
            lines.append(f"  ~ {redact_provider_text(old.model_id)}:")
            if added:
                lines.append(f"      +added: {redact_provider_text(added)}")
            if removed:
                lines.append(f"      -removed: {redact_provider_text(removed)}")
        lines.append("")

    if report.pricing_or_policy_changes:
        lines.append("### Pricing/Policy/Endpoint Changes")
        for old, new in report.pricing_or_policy_changes:
            lines.append(
                f"  ~ {redact_provider_text(old.model_id)}: "
                f"pricing {old.pricing}->{new.pricing}, "
                f"endpoints {old.endpoint_count}->{new.endpoint_count}"
            )
        lines.append("")

    if report.watchlist_models:
        lines.append("### Watchlist (requires evidence)")
        for model in report.watchlist_models:
            lines.append(
                f"  ? {redact_provider_text(model.model_id)}: "
                f"{redact_provider_text(model.privacy_note)}"
            )
        lines.append("")

    if report.needs_review:
        lines.append("### Needs Manual Review")
        for model in report.needs_review:
            lines.append(f"  * {redact_provider_text(model.model_id)}")
        lines.append("")

    if not any(
        [
            report.routing_impacted,
            report.new_free_models,
            report.removed_models,
            report.capability_changes,
            report.pricing_or_policy_changes,
            report.watchlist_models,
        ]
    ):
        lines.append("No changes detected.")

    return "\n".join(lines)
