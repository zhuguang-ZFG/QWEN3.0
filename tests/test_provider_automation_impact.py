"""Provider automation routing impact smoke tests."""

from provider_automation.catalog import ProviderModelEntry
from provider_automation.impact import check_impact, check_removal_impact, format_impact_smoke


def test_check_impact_new_free_model():
    models = [ProviderModelEntry(model_id="new_free", provider="x", pricing="free", endpoint_count=1)]
    smoke = check_impact(models, currently_routed=set())
    assert len(smoke.safe_additions) == 1
    assert smoke.safe_additions[0].model_id == "new_free"


def test_check_impact_paid_model_warns():
    models = [ProviderModelEntry(model_id="paid_model", provider="x", pricing="paid")]
    smoke = check_impact(models, currently_routed=set())
    assert len(smoke.critical) == 1
    assert any("billing" in w for w in smoke.critical[0].warnings)


def test_check_impact_privacy_watchlist():
    models = [ProviderModelEntry(model_id="suspicious", provider="x", privacy_note="prompts logged")]
    smoke = check_impact(models, currently_routed=set())
    assert len(smoke.critical) == 1


def test_check_impact_routed_model_flagged():
    models = [ProviderModelEntry(model_id="existing", provider="x")]
    smoke = check_impact(models, currently_routed={"existing"})
    assert smoke.results[0].in_routing is True


def test_check_removal_impact_routed():
    models = [ProviderModelEntry(model_id="routed_gone", provider="x")]
    smoke = check_removal_impact(models, currently_routed={"routed_gone"})
    assert len(smoke.critical) == 1
    assert any("cool/disable" in w for w in smoke.critical[0].warnings)


def test_format_impact_smoke():
    models = [ProviderModelEntry(model_id="safe", provider="x", pricing="free", endpoint_count=1)]
    smoke = check_impact(models, currently_routed=set())
    text = format_impact_smoke(smoke)
    assert "safe" in text
    assert "Safe Additions" in text


# M14: Review bundle


def test_check_removal_impact_pool_only_model_warns():
    models = [ProviderModelEntry(model_id="pool_gone", provider="x")]
    smoke = check_removal_impact(
        models,
        currently_routed=set(),
        pools={"coding": {"free": ["pool_gone"]}},
    )

    assert smoke.results[0].in_routing is True
    assert len(smoke.critical) == 1
    assert any("cool/disable" in warning for warning in smoke.critical[0].warnings)


def test_format_impact_smoke_redacts_secret_like_values():
    models = [
        ProviderModelEntry(
            model_id="sk-impact",
            provider="x",
            pricing="free",
            endpoint_count=1,
            privacy_note="token=secret",
        )
    ]
    smoke = check_impact(models, currently_routed=set())

    text = format_impact_smoke(smoke)

    assert "[REDACTED]" in text
    assert "sk-impact" not in text
    assert "token=secret" not in text
