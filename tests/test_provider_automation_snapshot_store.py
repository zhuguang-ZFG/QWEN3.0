"""Snapshot store persistence tests."""

import os

from provider_automation.catalog import ProviderModelEntry, ProviderModelSnapshot
from provider_automation.snapshot_store import (
    count_snapshots,
    list_snapshots,
    load_latest_snapshot,
    load_snapshot,
    reset_snapshots,
    save_snapshot,
)


def test_save_and_load_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(
        provider="openrouter",
        source="fixture",
        models=[
            ProviderModelEntry(model_id="m1", provider="openrouter"),
            ProviderModelEntry(model_id="m2", provider="openrouter"),
        ],
    )
    path = save_snapshot(snap)
    assert os.path.exists(path)

    loaded = load_snapshot(path)
    assert loaded is not None
    assert loaded.provider == "openrouter"
    assert loaded.model_ids() == {"m1", "m2"}


def test_load_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap1 = ProviderModelSnapshot(
        provider="openrouter",
        source="f",
        fetched_at=100,
        models=[
            ProviderModelEntry(model_id="old", provider="openrouter"),
        ],
    )
    snap2 = ProviderModelSnapshot(
        provider="openrouter",
        source="f",
        fetched_at=200,
        models=[
            ProviderModelEntry(model_id="new", provider="openrouter"),
        ],
    )
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
        snap = ProviderModelSnapshot(
            provider="or",
            source="f",
            models=[
                ProviderModelEntry(model_id=f"m{i}", provider="or"),
            ],
        )
        snap.fetched_at = 100 + i  # distinct timestamps
        save_snapshot(snap)
    assert count_snapshots("or") == 3
    assert len(list_snapshots("or")) == 3


def test_reset_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(
        provider="or",
        source="f",
        models=[
            ProviderModelEntry(model_id="m1", provider="or"),
        ],
    )
    save_snapshot(snap)
    reset_snapshots("or")
    assert count_snapshots("or") == 0


def test_snapshot_provider_name_is_sanitized_and_stays_in_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap = ProviderModelSnapshot(
        provider="../bad/provider",
        source="f",
        models=[
            ProviderModelEntry(model_id="m1", provider="../bad/provider"),
        ],
    )

    path = save_snapshot(snap)

    assert os.path.dirname(path) == str(tmp_path)
    assert ".." not in os.path.basename(path)
    assert "/" not in os.path.basename(path)
    assert "\\" not in os.path.basename(path)
    assert load_snapshot(path).provider == "../bad/provider"


def test_snapshot_same_second_saves_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    snap1 = ProviderModelSnapshot(
        provider="or",
        source="f",
        fetched_at=100,
        models=[
            ProviderModelEntry(model_id="m1", provider="or"),
        ],
    )
    snap2 = ProviderModelSnapshot(
        provider="or",
        source="f",
        fetched_at=100,
        models=[
            ProviderModelEntry(model_id="m2", provider="or"),
        ],
    )

    path1 = save_snapshot(snap1)
    path2 = save_snapshot(snap2)

    assert path1 != path2
    assert count_snapshots("or") == 2


def test_reset_snapshots_without_provider_removes_all(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_SNAPSHOT_DIR", str(tmp_path))
    for provider in ("a", "b"):
        save_snapshot(
            ProviderModelSnapshot(
                provider=provider,
                source="f",
                models=[
                    ProviderModelEntry(model_id=f"{provider}-m", provider=provider),
                ],
            )
        )

    reset_snapshots()

    assert count_snapshots("") == 0
