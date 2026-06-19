"""ModelAdmissionStatus/ProbeLevel/catalog tests."""

import pytest

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
    ProviderModelSnapshot,
)


def test_admission_status_values():
    assert ModelAdmissionStatus.UNKNOWN == "unknown"
    assert ModelAdmissionStatus.REJECTED == "rejected"
    assert ModelAdmissionStatus.WATCHLIST == "watchlist"
    assert ModelAdmissionStatus.SANDBOX_ONLY == "sandbox_only"
    assert ModelAdmissionStatus.CANDIDATE == "candidate"
    assert ModelAdmissionStatus.ROUTING_ENABLED == "routing_enabled"


def test_probe_level_values():
    assert ProbeLevel.METADATA_ONLY == "metadata_only"
    assert ProbeLevel.COMPLETION_SMOKE == "completion_smoke"
    assert ProbeLevel.STREAM_SMOKE == "stream_smoke"
    assert ProbeLevel.CODING_FIXTURE == "coding_fixture"
    assert ProbeLevel.QUALITY_GATE == "quality_gate"


def test_catalog_presence_does_not_imply_routing():
    entry = ProviderModelEntry(model_id="suspicious_model", provider="test")
    snapshot = ProviderModelSnapshot(provider="test", source="fixture", models=[entry])

    assert snapshot.get("suspicious_model").is_routeable is False
    assert snapshot.get("suspicious_model").admission_status is ModelAdmissionStatus.UNKNOWN
