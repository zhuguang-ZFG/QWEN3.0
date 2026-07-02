"""Batch runner for provider model probes.

Default configuration requests metadata and completion smoke checks. Coding
fixtures and quality gates require explicit flags. The runner never promotes a
model to routing_enabled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
    redact_provider_text,
)
from provider_automation.probe import (
    ProbeResult,
    determine_final_status,
    probe_coding_fixture,
    probe_completion_smoke,
    probe_metadata,
    probe_quality_gate,
    probe_stream_smoke,
)


_LEVEL_ORDER = {
    ProbeLevel.METADATA_ONLY: 0,
    ProbeLevel.COMPLETION_SMOKE: 1,
    ProbeLevel.STREAM_SMOKE: 2,
    ProbeLevel.CODING_FIXTURE: 3,
    ProbeLevel.QUALITY_GATE: 4,
}


@dataclass
class BatchProbeResult:
    model: ProviderModelEntry
    results: list[ProbeResult] = field(default_factory=list)
    final_status: ModelAdmissionStatus = ModelAdmissionStatus.UNKNOWN
    highest_level_passed: ProbeLevel = ProbeLevel.METADATA_ONLY


@dataclass
class ProbeRunnerConfig:
    run_metadata: bool = True
    run_completion_smoke: bool = True
    run_stream_smoke: bool = False
    run_coding_fixture: bool = False
    run_quality_gate: bool = False


SmokeCallable = Callable[[ProviderModelEntry, list[dict[str, str]], int], str]
StreamCallable = Callable[[ProviderModelEntry, list[dict[str, str]], int], list[str]]
CodingCallable = Callable[[ProviderModelEntry, list[Any]], tuple[int, int]]
QualityCallable = Callable[[ProviderModelEntry], float]


class ProbeRunner:
    """Batch probe runner with configurable levels."""

    def __init__(self, config: ProbeRunnerConfig | None = None) -> None:
        self.config = config or ProbeRunnerConfig()
        self._smoke_fn: SmokeCallable | None = None
        self._stream_fn: StreamCallable | None = None
        self._coding_fn: CodingCallable | None = None
        self._quality_fn: QualityCallable | None = None

    def set_smoke_callable(self, fn: SmokeCallable) -> None:
        self._smoke_fn = fn

    def set_stream_callable(self, fn: StreamCallable) -> None:
        self._stream_fn = fn

    def set_coding_callable(self, fn: CodingCallable) -> None:
        self._coding_fn = fn

    def set_quality_callable(self, fn: QualityCallable) -> None:
        self._quality_fn = fn

    def run(self, models: list[ProviderModelEntry]) -> list[BatchProbeResult]:
        return [self._probe_one(model) for model in models]

    def _probe_one(self, model: ProviderModelEntry) -> BatchProbeResult:
        results: list[ProbeResult] = []

        if self.config.run_metadata:
            results.append(probe_metadata(model))

        if results and results[-1].status is ModelAdmissionStatus.REJECTED:
            return _batch_result(model, results)

        if self.config.run_completion_smoke:
            results.append(self._run_completion_smoke(model))
        if self.config.run_stream_smoke:
            results.append(self._run_stream_smoke(model))
        if self.config.run_coding_fixture:
            results.append(self._run_coding_fixture(model))
        if self.config.run_quality_gate:
            results.append(self._run_quality_gate(model))

        return _batch_result(model, results)

    def _run_completion_smoke(self, model: ProviderModelEntry) -> ProbeResult:
        """Run the completion smoke check, guarding against missing or failing callables."""
        if self._smoke_fn is None:
            return _missing_callable_result(model, ProbeLevel.COMPLETION_SMOKE)
        try:
            text = self._smoke_fn(model, [{"role": "user", "content": "hi"}], 64)
            return probe_completion_smoke(text, model)
        except Exception as exc:
            return _exception_result(model, ProbeLevel.COMPLETION_SMOKE, exc)

    def _run_stream_smoke(self, model: ProviderModelEntry) -> ProbeResult:
        """Run the streaming smoke check, guarding against missing or failing callables."""
        if self._stream_fn is None:
            return _missing_callable_result(model, ProbeLevel.STREAM_SMOKE)
        try:
            chunks = self._stream_fn(model, [{"role": "user", "content": "hi"}], 64)
            return probe_stream_smoke(chunks, model)
        except Exception as exc:
            return _exception_result(model, ProbeLevel.STREAM_SMOKE, exc)

    def _run_coding_fixture(self, model: ProviderModelEntry) -> ProbeResult:
        """Run the coding fixture check, guarding against missing or failing callables."""
        if self._coding_fn is None:
            return _missing_callable_result(model, ProbeLevel.CODING_FIXTURE)
        try:
            passed, total = self._coding_fn(model, [])
            return probe_coding_fixture(passed, total, model)
        except Exception as exc:
            return _exception_result(model, ProbeLevel.CODING_FIXTURE, exc)

    def _run_quality_gate(self, model: ProviderModelEntry) -> ProbeResult:
        """Run the quality gate check, guarding against missing or failing callables."""
        if self._quality_fn is None:
            return _missing_callable_result(model, ProbeLevel.QUALITY_GATE)
        try:
            score = self._quality_fn(model)
            return probe_quality_gate(score, model)
        except Exception as exc:
            return _exception_result(model, ProbeLevel.QUALITY_GATE, exc)


def _missing_callable_result(model: ProviderModelEntry, level: ProbeLevel) -> ProbeResult:
    return ProbeResult(
        model=model,
        level=level,
        passed=False,
        status=ModelAdmissionStatus.WATCHLIST,
        error=f"{level.value} requested but callable is not configured",
    )


def _exception_result(
    model: ProviderModelEntry,
    level: ProbeLevel,
    exc: Exception,
) -> ProbeResult:
    return ProbeResult(
        model=model,
        level=level,
        passed=False,
        status=ModelAdmissionStatus.REJECTED,
        error=str(exc)[:200],
    )


def _batch_result(
    model: ProviderModelEntry,
    results: list[ProbeResult],
) -> BatchProbeResult:
    highest = ProbeLevel.METADATA_ONLY
    for result in results:
        if result.passed and _LEVEL_ORDER[result.level] > _LEVEL_ORDER[highest]:
            highest = result.level
    return BatchProbeResult(
        model=model,
        results=results,
        final_status=determine_final_status(results),
        highest_level_passed=highest,
    )


def _cell(value: str) -> str:
    text = redact_provider_text(value)
    return text.replace("|", "\\|").replace("\n", " ")


def format_batch_results(results: list[BatchProbeResult]) -> str:
    lines = ["## Probe Results", ""]
    lines.append("| Model | Status | Highest Pass | Details |")
    lines.append("|-------|--------|-------------|---------|")
    for batch_result in results:
        details = []
        for result in batch_result.results:
            if not result.passed:
                details.append(f"{result.level.value}: {result.error}")
        detail_str = "; ".join(details[:2]) if details else "ok"
        lines.append(
            f"| {_cell(batch_result.model.model_id)} | "
            f"{batch_result.final_status.value} | "
            f"{batch_result.highest_level_passed.value} | {_cell(detail_str)} |"
        )
    return "\n".join(lines)
