"""Provider automation catalog, snapshot store, and delta tests."""

import os

import pytest

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
    ProviderModelSnapshot,
    compute_delta,
)
from provider_automation.snapshot_store import (
    count_snapshots,
    list_snapshots,
    load_latest_snapshot,
    load_snapshot,
    reset_snapshots,
    save_snapshot,
)

from provider_automation_helpers import entry

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


def test_snapshot_model_ids_and_get():
    snapshot = ProviderModelSnapshot(
        provider="test",
        source="fixture",
        models=[entry("a"), entry("b"), entry("c")],
    )

    assert snapshot.model_ids() == {"a", "b", "c"}
    assert snapshot.get("b").model_id == "b"
    assert snapshot.get("missing") is None


def test_snapshot_rejects_mixed_provider_entries():
    with pytest.raises(ValueError, match="different provider"):
        ProviderModelSnapshot(
            provider="a",
            source="fixture",
            models=[ProviderModelEntry(model_id="m", provider="b")],
        )


def test_snapshot_round_trip():
    snapshot = ProviderModelSnapshot(
        provider="test",
        source="fixture",
        fetched_at=123.0,
        models=[entry("a", pricing="free", context_window=4096)],
    )

    restored = ProviderModelSnapshot.from_dict(snapshot.to_dict())
    assert restored.provider == "test"
    assert restored.source == "fixture"
    assert restored.fetched_at == 123.0
    assert restored.get("a").context_window == 4096


def test_delta_no_changes():
    old = ProviderModelSnapshot(provider="p", source="f", models=[entry("m1", provider="p")])
    new = ProviderModelSnapshot(provider="p", source="f", models=[entry("m1", provider="p")])

    delta = compute_delta(old, new)

    assert delta.has_changes is False
    assert [model.model_id for model in delta.unchanged] == ["m1"]
    assert delta.added == []
    assert delta.removed == []


def test_delta_added_removed_are_deterministic():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("c", provider="p"), entry("a", provider="p")],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("b", provider="p"), entry("d", provider="p")],
    )

    delta = compute_delta(old, new)

    assert [model.model_id for model in delta.added] == ["b", "d"]
    assert [model.model_id for model in delta.removed] == ["a", "c"]


def test_delta_changed_pricing_context_endpoint_and_probe_state():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[
            entry(
                "m1",
                provider="p",
                pricing="free",
                context_window=4096,
                endpoint_count=1,
                admission_status=ModelAdmissionStatus.UNKNOWN,
            )
        ],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[
            entry(
                "m1",
                provider="p",
                pricing="paid",
                context_window=8192,
                endpoint_count=0,
                admission_status=ModelAdmissionStatus.WATCHLIST,
            )
        ],
    )

    delta = compute_delta(old, new)

    assert delta.has_changes is True
    assert len(delta.changed) == 1


def test_delta_capabilities_order_does_not_count_as_change():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("m1", provider="p", capabilities=["code", "json"])],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("m1", provider="p", capabilities=["json", "code"])],
    )

    delta = compute_delta(old, new)

    assert delta.has_changes is False


def test_delta_privacy_note_change_is_detected():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("m1", provider="p", privacy_note="")],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[entry("m1", provider="p", privacy_note="prompts may be logged")],
    )

    assert compute_delta(old, new).has_changes is True


def test_delta_summary_includes_added_and_removed_models():
    old = ProviderModelSnapshot(
        provider="openrouter",
        source="f",
        models=[ProviderModelEntry(model_id="gone", provider="openrouter")],
    )
    new = ProviderModelSnapshot(
        provider="openrouter",
        source="f",
        models=[
            ProviderModelEntry(
                model_id="elephant-alpha",
                provider="openrouter",
                pricing="free",
                context_window=4096,
            )
        ],
    )

    text = compute_delta(old, new).summary()

    assert "Added:    1" in text
    assert "Removed:  1" in text
    assert "elephant-alpha" in text
    assert "gone" in text


def test_compute_delta_rejects_different_providers():
    old = ProviderModelSnapshot(
        provider="a",
        source="f",
        models=[ProviderModelEntry(model_id="shared_name", provider="a")],
    )
    new = ProviderModelSnapshot(
        provider="b",
        source="f",
        models=[ProviderModelEntry(model_id="shared_name", provider="b")],
    )

    with pytest.raises(ValueError, match="different providers"):
        compute_delta(old, new)


# M14: Snapshot store

from provider_automation.snapshot_store import (
    save_snapshot, load_snapshot, load_latest_snapshot,
    list_snapshots, count_snapshots, reset_snapshots,
)
import os


def test_save_and_load_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(provider="openrouter", source="fixture", models=[
        ProviderModelEntry(model_id="m1", provider="openrouter"),
        ProviderModelEntry(model_id="m2", provider="openrouter"),
    ])
    path = save_snapshot(snap)
    assert os.path.exists(path)

    loaded = load_snapshot(path)
    assert loaded is not None
    assert loaded.provider == "openrouter"
    assert loaded.model_ids() == {"m1", "m2"}


def test_load_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap1 = ProviderModelSnapshot(provider="openrouter", source="f",
                                  fetched_at=100, models=[
        ProviderModelEntry(model_id="old", provider="openrouter"),
    ])
    snap2 = ProviderModelSnapshot(provider="openrouter", source="f",
                                  fetched_at=200, models=[
        ProviderModelEntry(model_id="new", provider="openrouter"),
    ])
    save_snapshot(snap1)
    save_snapshot(snap2)
    latest = load_latest_snapshot("openrouter")
    assert latest is not None
    assert latest.model_ids() == {"new"}


def test_load_snapshot_bad_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert load_snapshot(str(bad)) is None


def test_list_and_count_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    for i in range(3):
        snap = ProviderModelSnapshot(provider="or", source="f", models=[
            ProviderModelEntry(model_id=f"m{i}", provider="or"),
        ])
        snap.fetched_at = 100 + i  # distinct timestamps
        save_snapshot(snap)
    assert count_snapshots("or") == 3
    assert len(list_snapshots("or")) == 3


def test_reset_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(provider="or", source="f", models=[
        ProviderModelEntry(model_id="m1", provider="or"),
    ])
    save_snapshot(snap)
    reset_snapshots("or")
    assert count_snapshots("or") == 0


# M14: Probe runner

def test_snapshot_provider_name_is_sanitized_and_stays_in_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(provider="../bad/provider", source="f", models=[
        ProviderModelEntry(model_id="m1", provider="../bad/provider"),
    ])

    path = save_snapshot(snap)

    assert os.path.dirname(path) == str(tmp_path)
    assert ".." not in os.path.basename(path)
    assert "/" not in os.path.basename(path)
    assert "\\" not in os.path.basename(path)
    assert load_snapshot(path).provider == "../bad/provider"


def test_snapshot_same_second_saves_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap1 = ProviderModelSnapshot(provider="or", source="f", fetched_at=100, models=[
        ProviderModelEntry(model_id="m1", provider="or"),
    ])
    snap2 = ProviderModelSnapshot(provider="or", source="f", fetched_at=100, models=[
        ProviderModelEntry(model_id="m2", provider="or"),
    ])

    path1 = save_snapshot(snap1)
    path2 = save_snapshot(snap2)

    assert path1 != path2
    assert count_snapshots("or") == 2


def test_reset_snapshots_without_provider_removes_all(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    for provider in ("a", "b"):
        save_snapshot(ProviderModelSnapshot(provider=provider, source="f", models=[
            ProviderModelEntry(model_id=f"{provider}-m", provider=provider),
        ]))

    reset_snapshots()

    assert count_snapshots("") == 0
