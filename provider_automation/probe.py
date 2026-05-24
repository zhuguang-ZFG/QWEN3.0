"""Tiered provider model probe helpers.

The probe harness classifies evidence only. It never promotes a model to
``routing_enabled``; that state is reserved for manual admission.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
    redact_provider_text,
)


@dataclass
class ProbeResult:
    model: ProviderModelEntry
    level: ProbeLevel
    passed: bool
    status: ModelAdmissionStatus
    latency_ms: float = 0.0
    error: str = ""
    evidence: dict = field(default_factory=dict)
    output_preview: str = ""

    def __post_init__(self) -> None:
        if self.status is ModelAdmissionStatus.ROUTING_ENABLED:
            raise ValueError("probe result cannot enable routing")
        self.error = redact_provider_text(self.error)
        self.output_preview = redact_provider_text(self.output_preview[:100])


@dataclass
class ModelProbeReport:
    model: ProviderModelEntry
    results: list[ProbeResult] = field(default_factory=list)
    final_status: ModelAdmissionStatus = ModelAdmissionStatus.UNKNOWN

    @property
    def passed_all(self) -> bool:
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def failed_at(self) -> ProbeLevel | None:
        for result in self.results:
            if not result.passed:
                return result.level
        return None


def probe_metadata(model: ProviderModelEntry) -> ProbeResult:
    """Run static metadata checks without network access."""
    if not model.model_id or not model.provider:
        return ProbeResult(
            model=model,
            level=ProbeLevel.METADATA_ONLY,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="missing model_id or provider",
        )

    issues: list[str] = []
    if model.privacy_note:
        issues.append(f"watchlist: {model.privacy_note}")
    if model.pricing == "paid":
        issues.append("paid model requires cost review")
    if model.endpoint_count <= 0:
        issues.append("no known endpoints")

    if issues:
        return ProbeResult(
            model=model,
            level=ProbeLevel.METADATA_ONLY,
            passed=False,
            status=ModelAdmissionStatus.WATCHLIST,
            error="; ".join(issues),
            evidence={"issues": issues},
        )

    return ProbeResult(
        model=model,
        level=ProbeLevel.METADATA_ONLY,
        passed=True,
        status=ModelAdmissionStatus.SANDBOX_ONLY,
        evidence={"issues": []},
    )


def probe_completion_smoke(response_text: str, model: ProviderModelEntry) -> ProbeResult:
    """Evaluate a harmless completion smoke response."""
    text = response_text or ""
    if not text.strip():
        return ProbeResult(
            model=model,
            level=ProbeLevel.COMPLETION_SMOKE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="empty response",
        )
    if len(text.strip()) < 5:
        return ProbeResult(
            model=model,
            level=ProbeLevel.COMPLETION_SMOKE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="response too short",
            output_preview=text,
        )

    lower = text.lower()
    for marker in (
        "model not found",
        "quota exceeded",
        "rate limit",
        "service unavailable",
        "unauthorized",
    ):
        if marker in lower:
            return ProbeResult(
                model=model,
                level=ProbeLevel.COMPLETION_SMOKE,
                passed=False,
                status=ModelAdmissionStatus.REJECTED,
                error=f"response contains error marker: {marker}",
                output_preview=text,
            )

    return ProbeResult(
        model=model,
        level=ProbeLevel.COMPLETION_SMOKE,
        passed=True,
        status=ModelAdmissionStatus.SANDBOX_ONLY,
        output_preview=text,
    )


def probe_stream_smoke(
    chunks: list[str],
    model: ProviderModelEntry,
    latency_ms: float = 0.0,
) -> ProbeResult:
    """Evaluate a harmless streaming smoke response."""
    if not chunks:
        return ProbeResult(
            model=model,
            level=ProbeLevel.STREAM_SMOKE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="no chunks received",
            latency_ms=latency_ms,
        )

    total_text = "".join(chunks)
    if len(total_text.strip()) < 5:
        return ProbeResult(
            model=model,
            level=ProbeLevel.STREAM_SMOKE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="stream output too short",
            latency_ms=latency_ms,
            output_preview=total_text,
        )

    return ProbeResult(
        model=model,
        level=ProbeLevel.STREAM_SMOKE,
        passed=True,
        status=ModelAdmissionStatus.SANDBOX_ONLY,
        latency_ms=latency_ms,
        evidence={"chunk_count": len(chunks), "total_chars": len(total_text)},
        output_preview=total_text,
    )


def probe_coding_fixture(
    passed_cases: int,
    total_cases: int,
    model: ProviderModelEntry,
) -> ProbeResult:
    """Evaluate synthetic coding fixture results."""
    if total_cases <= 0:
        return ProbeResult(
            model=model,
            level=ProbeLevel.CODING_FIXTURE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="no cases evaluated",
        )

    ratio = max(0.0, min(1.0, passed_cases / total_cases))
    evidence = {"passed": passed_cases, "total": total_cases, "ratio": ratio}
    if ratio >= 0.8:
        return ProbeResult(
            model=model,
            level=ProbeLevel.CODING_FIXTURE,
            passed=True,
            status=ModelAdmissionStatus.CANDIDATE,
            evidence=evidence,
        )
    if ratio >= 0.5:
        return ProbeResult(
            model=model,
            level=ProbeLevel.CODING_FIXTURE,
            passed=True,
            status=ModelAdmissionStatus.SANDBOX_ONLY,
            evidence=evidence,
        )
    return ProbeResult(
        model=model,
        level=ProbeLevel.CODING_FIXTURE,
        passed=False,
        status=ModelAdmissionStatus.REJECTED,
        error=f"coding pass rate {ratio:.0%} below threshold",
        evidence=evidence,
    )


def probe_quality_gate(score: float, model: ProviderModelEntry) -> ProbeResult:
    """Evaluate quality gate score from a synthetic eval."""
    bounded_score = max(0.0, min(1.0, float(score)))
    evidence = {"score": bounded_score}
    if bounded_score >= 0.8:
        return ProbeResult(
            model=model,
            level=ProbeLevel.QUALITY_GATE,
            passed=True,
            status=ModelAdmissionStatus.CANDIDATE,
            evidence=evidence,
        )
    if bounded_score >= 0.6:
        return ProbeResult(
            model=model,
            level=ProbeLevel.QUALITY_GATE,
            passed=True,
            status=ModelAdmissionStatus.SANDBOX_ONLY,
            evidence=evidence,
        )
    return ProbeResult(
        model=model,
        level=ProbeLevel.QUALITY_GATE,
        passed=False,
        status=ModelAdmissionStatus.REJECTED,
        error=f"quality score {bounded_score:.2f} below threshold",
        evidence=evidence,
    )


def determine_final_status(results: list[ProbeResult]) -> ModelAdmissionStatus:
    """Determine final admission status from probe results."""
    if not results:
        return ModelAdmissionStatus.UNKNOWN

    statuses = {result.status for result in results}
    if ModelAdmissionStatus.ROUTING_ENABLED in statuses:
        raise ValueError("probe pipeline cannot produce routing_enabled")
    if ModelAdmissionStatus.REJECTED in statuses:
        return ModelAdmissionStatus.REJECTED
    if ModelAdmissionStatus.WATCHLIST in statuses:
        return ModelAdmissionStatus.WATCHLIST
    if statuses == {ModelAdmissionStatus.CANDIDATE}:
        return ModelAdmissionStatus.CANDIDATE
    return ModelAdmissionStatus.SANDBOX_ONLY
