"""Human review bundle for provider model automation.

The bundle is a self-contained markdown package for operator review. It never
changes routing state or edits backends.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from provider_automation.admission import PatchPlan, format_patch_plan
from provider_automation.catalog import (
    ProviderCatalogDelta,
    redact_provider_text,
)
from provider_automation.runner import BatchProbeResult


@dataclass
class ReviewBundle:
    provider: str
    delta_summary: str = ""
    change_report: str = ""
    probe_results: str = ""
    patch_plan: str = ""
    impact_smoke: str = ""
    generated_at: str = ""

    def to_markdown(self) -> str:
        sections = [
            f"# Provider Review Bundle: {_line(self.provider)}",
            f"Generated: {_line(self.generated_at)}",
            "",
            "## Catalog Changes",
            _block(self.delta_summary) or "No delta available.",
            "",
            _block(self.change_report) or "No change report.",
            "",
            "## Probe Results",
            _block(self.probe_results) or "No probes run.",
            "",
            "## Routing Impact",
            _block(self.impact_smoke) or "No impact analysis.",
            "",
            "## Patch Plan",
            _block(self.patch_plan) or "No patch plan.",
            "",
            "## Actions Required",
            "1. Review each proposed addition against probe evidence",
            "2. Check watchlist models for endpoint_count and privacy policy",
            "3. Verify removed models are not still receiving traffic",
            "4. **Do NOT auto-modify backends.py** - apply changes manually after review",
        ]
        return "\n".join(sections)


def build_review_bundle(
    delta: ProviderCatalogDelta,
    probe_results: list[BatchProbeResult] | None = None,
    patch_plan: PatchPlan | None = None,
    impact_text: str = "",
    delta_summary: str = "",
    change_report_text: str = "",
) -> ReviewBundle:
    return ReviewBundle(
        provider=delta.provider,
        delta_summary=delta_summary or delta.summary(),
        change_report=change_report_text,
        probe_results=_format_probe_section(probe_results or []),
        patch_plan=format_patch_plan(patch_plan) if patch_plan else "",
        impact_smoke=impact_text,
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    )


def _format_probe_section(results: list[BatchProbeResult]) -> str:
    if not results:
        return "No probe results."
    lines = ["| Model | Status | Highest Pass |", "|-------|--------|-------------|"]
    for batch_result in results:
        errors = [result.error for result in batch_result.results if not result.passed]
        detail = "; ".join(errors[:2]) if errors else "ok"
        lines.append(
            f"| {_cell(batch_result.model.model_id)} | "
            f"{batch_result.final_status.value} | "
            f"{batch_result.highest_level_passed.value} ({_cell(detail)}) |"
        )
    return "\n".join(lines)


def _block(value: str) -> str:
    return redact_provider_text(value)


def _line(value: str) -> str:
    return _block(value).replace("\n", " ")


def _cell(value: str) -> str:
    return _line(value).replace("|", "\\|")
