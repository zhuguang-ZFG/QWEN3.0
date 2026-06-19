"""ProviderModelSnapshot tests."""

import pytest

from provider_automation.catalog import ProviderModelEntry, ProviderModelSnapshot
from provider_automation_helpers import entry


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
