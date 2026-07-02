"""ProviderModelEntry tests."""

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
)


def test_model_entry_key():
    entry = ProviderModelEntry(model_id="gpt-4o", provider="openrouter")

    assert entry.key() == "openrouter:gpt-4o"


def test_model_entry_defaults_are_not_routeable():
    entry = ProviderModelEntry(model_id="test-model", provider="test")

    assert entry.pricing == "unknown"
    assert entry.context_window == 0
    assert entry.capabilities == []
    assert entry.admission_status is ModelAdmissionStatus.UNKNOWN
    assert entry.highest_probe_level is ProbeLevel.METADATA_ONLY
    assert entry.is_routeable is False


def test_model_entry_routeable_only_when_manually_enabled():
    entry = ProviderModelEntry(
        model_id="safe-model",
        provider="test",
        admission_status=ModelAdmissionStatus.ROUTING_ENABLED,
    )

    assert entry.is_routeable is True


def test_model_entry_round_trip_redacts_secret_metadata():
    entry = ProviderModelEntry(
        model_id="m1",
        provider="test",
        display_name="Model",
        context_window=8192,
        pricing="free",
        capabilities=["json", "code"],
        endpoint_count=2,
        admission_status=ModelAdmissionStatus.CANDIDATE,
        highest_probe_level=ProbeLevel.QUALITY_GATE,
        evidence_refs=["safe-ref", "Bearer secret-token"],
        source_evidence="api_key=secret",
        raw_metadata={
            "description": "public",
            "api_key": "sk-test",
            "nested": {"token": "secret", "safe": "ok"},
        },
    )

    serialized = entry.to_dict()
    assert serialized["raw_metadata"]["api_key"] == "[REDACTED]"
    assert serialized["raw_metadata"]["nested"]["token"] == "[REDACTED]"
    assert serialized["raw_metadata"]["nested"]["safe"] == "ok"
    assert serialized["evidence_refs"] == ["safe-ref", "[REDACTED]"]
    assert serialized["source_evidence"] == "[REDACTED]"

    restored = ProviderModelEntry.from_dict(serialized)
    assert restored.model_id == "m1"
    assert restored.provider == "test"
    assert restored.admission_status is ModelAdmissionStatus.CANDIDATE
    assert restored.highest_probe_level is ProbeLevel.QUALITY_GATE


def test_model_entry_from_dict_ignores_unknown_fields_safely():
    entry = ProviderModelEntry.from_dict(
        {
            "model_id": "m1",
            "provider": "test",
            "unknown": "ignored",
            "admission_status": "not-a-status",
            "highest_probe_level": "not-a-level",
        }
    )

    assert entry.model_id == "m1"
    assert entry.admission_status is ModelAdmissionStatus.UNKNOWN
    assert entry.highest_probe_level is ProbeLevel.METADATA_ONLY
