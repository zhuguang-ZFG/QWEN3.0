"""build_review_bundle tests."""

from provider_automation.catalog import (
    ProviderModelEntry,
    ProviderModelSnapshot,
)
from provider_automation.review import build_review_bundle


def test_build_review_bundle():
    from provider_automation.catalog import compute_delta

    old = ProviderModelSnapshot(provider="or", source="f", models=[])
    new = ProviderModelSnapshot(
        provider="or",
        source="f",
        models=[
            ProviderModelEntry(model_id="new_model", provider="or", pricing="free", endpoint_count=1),
        ],
    )
    delta = compute_delta(old, new)
    bundle = build_review_bundle(delta, impact_text="no impact")
    md = bundle.to_markdown()
    assert "Provider Review Bundle" in md
    assert "or" in md
    assert "Actions Required" in md
    assert "Do NOT auto-modify backends.py" in md


def test_review_bundle_redacts_injected_secret_text():
    from provider_automation.catalog import compute_delta

    old = ProviderModelSnapshot(provider="or", source="f", models=[])
    new = ProviderModelSnapshot(
        provider="or",
        source="f",
        models=[
            ProviderModelEntry(model_id="safe", provider="or", pricing="free"),
        ],
    )
    delta = compute_delta(old, new)

    bundle = build_review_bundle(
        delta,
        impact_text="Bearer should not leak",
        delta_summary="api_key=secret",
        change_report_text="token=secret",
    )
    md = bundle.to_markdown()

    assert "[REDACTED]" in md
    assert "Bearer should not leak" not in md
    assert "api_key=secret" not in md
    assert "token=secret" not in md
