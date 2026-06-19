"""compute_delta tests."""

import pytest

from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProviderModelEntry,
    ProviderModelSnapshot,
    compute_delta,
)
from provider_automation_helpers import entry


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
