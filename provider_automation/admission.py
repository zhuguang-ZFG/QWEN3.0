"""Routing admission patch-plan generation.

This module never edits ``backends.py``. It produces reviewable plans that a
human can apply after checking probe evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProviderModelEntry,
    redact_provider_text,
)


@dataclass
class PatchPlan:
    provider: str
    additions: list[tuple[ProviderModelEntry, str]] = field(default_factory=list)
    removals: list[ProviderModelEntry] = field(default_factory=list)
    watchlist: list[tuple[ProviderModelEntry, str]] = field(default_factory=list)
    cool_disable: list[ProviderModelEntry] = field(default_factory=list)
    generated_by: str = "provider_automation"
    requires_approval: bool = True

    @property
    def is_empty(self) -> bool:
        return not any([self.additions, self.removals, self.watchlist, self.cool_disable])


def propose_additions(
    candidates: list[ProviderModelEntry],
    status_map: dict[str, ModelAdmissionStatus],
) -> PatchPlan:
    """Generate a patch plan for model additions."""
    provider = candidates[0].provider if candidates else ""
    plan = PatchPlan(provider=provider)
    for model in candidates:
        status = status_map.get(model.key(), ModelAdmissionStatus.UNKNOWN)
        if status is ModelAdmissionStatus.ROUTING_ENABLED:
            plan.watchlist.append((model, "routing_enabled must be set by manual review"))
        elif status is ModelAdmissionStatus.CANDIDATE:
            plan.additions.append((model, f"passed probe pipeline, status={status.value}"))
        elif status is ModelAdmissionStatus.WATCHLIST:
            plan.watchlist.append((model, model.privacy_note or "needs evidence"))
        elif status is ModelAdmissionStatus.SANDBOX_ONLY:
            plan.watchlist.append((model, "sandbox_only; probe passed but not yet routing"))
        elif status is ModelAdmissionStatus.REJECTED:
            plan.watchlist.append((model, "rejected by probe pipeline"))
    return plan


def propose_removals(
    currently_routed: set[str],
    delta_removed: list[ProviderModelEntry],
) -> PatchPlan:
    """Plan retirement for models removed from a provider catalog."""
    provider = delta_removed[0].provider if delta_removed else ""
    plan = PatchPlan(provider=provider)
    for model in delta_removed:
        if model.key() in currently_routed or model.model_id in currently_routed:
            plan.cool_disable.append(model)
        else:
            plan.removals.append(model)
    return plan


def merge_patch_plans(*plans: PatchPlan) -> PatchPlan:
    """Merge patch plans without dropping approval requirements."""
    merged = PatchPlan(provider=plans[0].provider if plans else "")
    for plan in plans:
        if not merged.provider:
            merged.provider = plan.provider
        merged.additions.extend(plan.additions)
        merged.removals.extend(plan.removals)
        merged.watchlist.extend(plan.watchlist)
        merged.cool_disable.extend(plan.cool_disable)
        merged.requires_approval = merged.requires_approval or plan.requires_approval
    return merged


def _format_additions_section(plan: PatchPlan) -> list[str]:
    """Render the "Proposed Additions" markdown section (or empty if none)."""
    if not plan.additions:
        return []
    lines = ["## Proposed Additions", "| Model | Reason |", "|-------|--------|"]
    for model, reason in plan.additions:
        caps = ", ".join(model.capabilities) if model.capabilities else "none"
        lines.append(
            f"| {redact_provider_text(model.model_id)} | "
            f"{redact_provider_text(reason)} (caps={redact_provider_text(caps)}) |"
        )
    lines.append("")
    return lines


def _format_cool_disable_section(plan: PatchPlan) -> list[str]:
    """Render the "Cool/Disable" markdown section (or empty if none)."""
    if not plan.cool_disable:
        return []
    lines = ["## Cool/Disable (removed from catalog, was in routing)"]
    for model in plan.cool_disable:
        lines.append(f"  - {redact_provider_text(model.model_id)}: disable in backends.py, do NOT delete")
    lines.append("")
    return lines


def _format_removals_section(plan: PatchPlan) -> list[str]:
    """Render the "Removals" markdown section (or empty if none)."""
    if not plan.removals:
        return []
    lines = ["## Removals (not in routing)"]
    for model in plan.removals:
        lines.append(f"  - {redact_provider_text(model.model_id)}")
    lines.append("")
    return lines


def _format_watchlist_section(plan: PatchPlan) -> list[str]:
    """Render the "Watchlist" markdown section (or empty if none)."""
    if not plan.watchlist:
        return []
    lines = ["## Watchlist (needs evidence)"]
    for model, reason in plan.watchlist:
        lines.append(f"  ? {redact_provider_text(model.model_id)}: {redact_provider_text(reason)}")
    lines.append("")
    return lines


def format_patch_plan(plan: PatchPlan) -> str:
    """Format a patch plan as safe markdown for human review."""
    lines = [
        f"# Routing Patch Plan: {redact_provider_text(plan.provider)}",
        f"Generated by: {redact_provider_text(plan.generated_by)}",
        f"Requires approval: {'YES' if plan.requires_approval else 'no'}",
        "",
    ]

    if plan.is_empty:
        lines.append("No changes proposed.")
        return "\n".join(lines)

    lines.extend(_format_additions_section(plan))
    lines.extend(_format_cool_disable_section(plan))
    lines.extend(_format_removals_section(plan))
    lines.extend(_format_watchlist_section(plan))

    lines.append("## Actions Required")
    lines.append("1. Human reviewer: check each proposed addition against probe evidence")
    lines.append("2. For cool/disable: set backend_enabled=False, add cooldown note")
    lines.append("3. For watchlist: gather endpoint_count, privacy note, source evidence")
    lines.append("4. After manual review, update backends.py and router_v3.POOLS")
    lines.append("5. Run: python -m pytest tests/test_backend_registry.py -q")
    return "\n".join(lines)
