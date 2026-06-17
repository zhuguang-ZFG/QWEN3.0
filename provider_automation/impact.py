"""Dry-run registry impact analysis for provider model changes.

Answers routing-impact questions without modifying backends.py or
router_v3.POOLS.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from provider_automation.catalog import ProviderModelEntry, redact_provider_text


@dataclass
class ImpactResult:
    model_id: str
    in_routing: bool = False
    in_pools: list[str] = field(default_factory=list)
    is_free: bool = True
    has_privacy_note: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImpactSmoke:
    provider: str
    results: list[ImpactResult] = field(default_factory=list)

    @property
    def critical(self) -> list[ImpactResult]:
        return [result for result in self.results if result.warnings]

    @property
    def safe_additions(self) -> list[ImpactResult]:
        return [
            result
            for result in self.results
            if not result.in_routing and result.is_free and not result.has_privacy_note and not result.warnings
        ]


def check_impact(
    candidates: list[ProviderModelEntry],
    currently_routed: set[str],
    pools: dict[str, dict[str, list[str]]] | None = None,
) -> ImpactSmoke:
    """Analyze candidate model impact against current routing state."""
    pools = pools or {}
    results = []

    for model in candidates:
        result = ImpactResult(model_id=model.model_id)

        if model.model_id in currently_routed or model.key() in currently_routed:
            result.in_routing = True

        _collect_pool_membership(result, model, pools)

        if model.pricing == "paid":
            result.is_free = False
            result.warnings.append("paid model - verify billing before routing")
        elif model.pricing == "unknown":
            result.warnings.append("unknown pricing - needs verification")

        if model.privacy_note:
            result.has_privacy_note = True
            result.warnings.append(f"privacy concern: {model.privacy_note}")

        if model.endpoint_count == 0:
            result.warnings.append("no known endpoints")

        results.append(result)

    return ImpactSmoke(provider=candidates[0].provider if candidates else "", results=results)


def check_removal_impact(
    removed_models: list[ProviderModelEntry],
    currently_routed: set[str],
    pools: dict[str, dict[str, list[str]]] | None = None,
) -> ImpactSmoke:
    """Analyze removed catalog models against current routing state."""
    pools = pools or {}
    results = []

    for model in removed_models:
        result = ImpactResult(model_id=model.model_id)
        if model.model_id in currently_routed or model.key() in currently_routed:
            result.in_routing = True

        _collect_pool_membership(result, model, pools)
        if result.in_routing:
            result.warnings.append("REMOVED from catalog but still in routing - cool/disable required")

        results.append(result)

    return ImpactSmoke(
        provider=removed_models[0].provider if removed_models else "",
        results=results,
    )


def _collect_pool_membership(
    result: ImpactResult,
    model: ProviderModelEntry,
    pools: dict[str, dict[str, list[str]]],
) -> None:
    for pool_name, tiers in pools.items():
        for tier_name, backends in tiers.items():
            if model.model_id in backends or model.key() in backends:
                result.in_pools.append(f"{pool_name}/{tier_name}")
                result.in_routing = True


def format_impact_smoke(smoke: ImpactSmoke) -> str:
    lines = [f"## Impact Smoke: {_line(smoke.provider)}", ""]

    if smoke.critical:
        lines.append("### Critical Warnings")
        for result in smoke.critical:
            for warning in result.warnings:
                lines.append(f"  ! {_line(result.model_id)}: {_line(warning)}")
        lines.append("")

    if smoke.safe_additions:
        lines.append("### Safe Additions (no concerns)")
        for result in smoke.safe_additions:
            lines.append(f"  + {_line(result.model_id)}")
        lines.append("")

    if not smoke.critical and not smoke.safe_additions:
        lines.append("No impact concerns detected.")

    lines.append("### Full Results")
    lines.append("| Model | In Routing | Free | Pools | Warnings |")
    lines.append("|-------|-----------|------|-------|----------|")
    for result in smoke.results:
        pools_str = ", ".join(result.in_pools) if result.in_pools else "none"
        warnings_str = "; ".join(result.warnings[:2]) if result.warnings else "none"
        lines.append(
            f"| {_cell(result.model_id)} | "
            f"{'YES' if result.in_routing else 'no'} | "
            f"{'yes' if result.is_free else 'NO'} | "
            f"{_cell(pools_str)} | {_cell(warnings_str)} |"
        )

    return "\n".join(lines)


def _line(value: str) -> str:
    return redact_provider_text(value).replace("\n", " ")


def _cell(value: str) -> str:
    return _line(value).replace("|", "\\|")
