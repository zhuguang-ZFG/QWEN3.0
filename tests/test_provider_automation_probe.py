"""Probe pipeline tests."""

import pytest

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
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
from provider_automation_helpers import entry


def test_probe_metadata_rejects_missing_and_watchlists_risky_metadata():
    missing = ProviderModelEntry(model_id="", provider="")
    paid = entry("paid", pricing="paid", endpoint_count=1)
    no_endpoint = entry("no-endpoint", pricing="free", endpoint_count=0)
    clean = entry("clean", pricing="free", endpoint_count=1)

    assert probe_metadata(missing).status is ModelAdmissionStatus.REJECTED
    assert probe_metadata(paid).status is ModelAdmissionStatus.WATCHLIST
    assert probe_metadata(paid).passed is False
    assert probe_metadata(no_endpoint).status is ModelAdmissionStatus.WATCHLIST
    assert probe_metadata(no_endpoint).passed is False
    assert probe_metadata(clean).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_metadata(clean).passed is True


def test_probe_completion_and_stream_smoke_classify_errors():
    model = entry("m", endpoint_count=1)

    assert probe_completion_smoke("", model).status is ModelAdmissionStatus.REJECTED
    assert probe_completion_smoke("quota exceeded", model).status is ModelAdmissionStatus.REJECTED
    assert probe_completion_smoke("exact safe response", model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_stream_smoke([], model).status is ModelAdmissionStatus.REJECTED
    assert probe_stream_smoke(["safe ", "stream"], model).status is ModelAdmissionStatus.SANDBOX_ONLY


def test_probe_coding_and_quality_thresholds():
    model = entry("m", endpoint_count=1)

    assert probe_coding_fixture(0, 0, model).status is ModelAdmissionStatus.REJECTED
    assert probe_coding_fixture(2, 4, model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_coding_fixture(4, 5, model).status is ModelAdmissionStatus.CANDIDATE
    assert probe_quality_gate(0.59, model).status is ModelAdmissionStatus.REJECTED
    assert probe_quality_gate(0.6, model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_quality_gate(0.8, model).status is ModelAdmissionStatus.CANDIDATE


def test_probe_pipeline_never_accepts_routing_enabled():
    model = entry("m")

    with pytest.raises(ValueError, match="cannot enable routing"):
        ProbeResult(
            model=model,
            level=ProbeLevel.QUALITY_GATE,
            passed=True,
            status=ModelAdmissionStatus.ROUTING_ENABLED,
        )


def test_determine_final_status_precedence():
    model = entry("m")
    rejected = ProbeResult(
        model=model,
        level=ProbeLevel.COMPLETION_SMOKE,
        passed=False,
        status=ModelAdmissionStatus.REJECTED,
    )
    watchlist = ProbeResult(
        model=model,
        level=ProbeLevel.METADATA_ONLY,
        passed=False,
        status=ModelAdmissionStatus.WATCHLIST,
    )
    candidate = ProbeResult(
        model=model,
        level=ProbeLevel.QUALITY_GATE,
        passed=True,
        status=ModelAdmissionStatus.CANDIDATE,
    )

    assert determine_final_status([]) is ModelAdmissionStatus.UNKNOWN
    assert determine_final_status([watchlist, candidate]) is ModelAdmissionStatus.WATCHLIST
    assert determine_final_status([candidate]) is ModelAdmissionStatus.CANDIDATE
    assert determine_final_status([watchlist, rejected]) is ModelAdmissionStatus.REJECTED
