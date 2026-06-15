"""Provider automation admission, probe pipeline, and patch plan tests."""

import asyncio

import pytest

from provider_automation.admission import (
    format_patch_plan,
    merge_patch_plans,
    propose_additions,
    propose_removals,
)
from provider_automation.catalog import (
    ModelAdmissionStatus,
    ProbeLevel,
    ProviderModelEntry,
    ProviderModelSnapshot,
    compute_delta,
)
from provider_automation.openrouter import (
    OpenRouterModel,
    create_empty_fixture,
    fetch_live,
    parse_fixture,
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
from provider_automation.report import build_change_report, format_change_report
from provider_automation.review import build_review_bundle

from provider_automation_helpers import entry

def test_build_review_bundle():
    from provider_automation.catalog import compute_delta
    old = ProviderModelSnapshot(provider="or", source="f", models=[])
    new = ProviderModelSnapshot(provider="or", source="f", models=[
        ProviderModelEntry(model_id="new_model", provider="or", pricing="free",
                          endpoint_count=1),
    ])
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
    new = ProviderModelSnapshot(provider="or", source="f", models=[
        ProviderModelEntry(model_id="safe", provider="or", pricing="free"),
    ])
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


def test_openrouter_fixture_parser_marks_elephant_watchlist(tmp_path):
    fixture_path = create_empty_fixture(str(tmp_path / "openrouter.json"))

    snapshot = parse_fixture(fixture_path)
    elephant = snapshot.get("elephant/alpha-experimental")

    assert snapshot.provider == "openrouter"
    assert elephant is not None
    assert elephant.pricing == "free"
    assert elephant.endpoint_count == 0
    assert elephant.admission_status is ModelAdmissionStatus.WATCHLIST
    assert "endpoint" in elephant.privacy_note


def test_openrouter_parser_does_not_assume_endpoints():
    entry = OpenRouterModel(
        id="openrouter/no-endpoints",
        name="No Endpoints",
        pricing={"prompt": "0", "completion": "0"},
    ).to_entry()

    assert entry.endpoint_count == 0
    assert entry.admission_status is ModelAdmissionStatus.WATCHLIST
    assert entry.is_routeable is False


def test_openrouter_live_fetch_gate_is_runtime(monkeypatch):
    monkeypatch.delenv("LIMA_OPENROUTER_LIVE_FETCH", raising=False)

    with pytest.raises(RuntimeError, match="LIMA_OPENROUTER_LIVE_FETCH=1"):
        import asyncio

        asyncio.run(fetch_live())


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


def test_change_report_tracks_routing_impacted_and_redacts_output():
    removed = ProviderModelEntry(model_id="sk-removed", provider="openrouter")
    added = ProviderModelEntry(
        model_id="new-free",
        provider="openrouter",
        pricing="free",
        privacy_note="Bearer should not leak",
    )
    delta = compute_delta(
        ProviderModelSnapshot(provider="openrouter", source="old", models=[removed]),
        ProviderModelSnapshot(provider="openrouter", source="new", models=[added]),
    )

    report = build_change_report(delta, currently_routed={removed.key()})
    text = format_change_report(report)

    assert report.routing_impacted == [removed]
    assert report.watchlist_models == [added]
    assert "[REDACTED]" in text
    assert "sk-removed" not in text
    assert "Bearer should not leak" not in text


def test_patch_plan_additions_require_candidate_status_and_redact():
    candidate = ProviderModelEntry(
        model_id="safe-model",
        provider="openrouter",
        capabilities=["code"],
    )
    routed = ProviderModelEntry(model_id="manual-only", provider="openrouter")
    watch = ProviderModelEntry(
        model_id="sk-watch",
        provider="openrouter",
        privacy_note="token=secret",
    )

    plan = propose_additions(
        [candidate, routed, watch],
        {
            candidate.key(): ModelAdmissionStatus.CANDIDATE,
            routed.key(): ModelAdmissionStatus.ROUTING_ENABLED,
            watch.key(): ModelAdmissionStatus.WATCHLIST,
        },
    )
    text = format_patch_plan(plan)

    assert [model.model_id for model, _ in plan.additions] == ["safe-model"]
    assert {model.model_id for model, _ in plan.watchlist} == {"manual-only", "sk-watch"}
    assert plan.requires_approval is True
    assert "[REDACTED]" in text
    assert "sk-watch" not in text
    assert "token=secret" not in text


def test_patch_plan_removals_cool_disable_routed_models():
    routed = ProviderModelEntry(model_id="routed", provider="openrouter")
    unrouted = ProviderModelEntry(model_id="unrouted", provider="openrouter")

    plan = propose_removals({routed.key()}, [routed, unrouted])

    assert plan.cool_disable == [routed]
    assert plan.removals == [unrouted]
    assert "do NOT delete" in format_patch_plan(plan)


def test_merge_patch_plans_preserves_all_sections():
    candidate = ProviderModelEntry(model_id="candidate", provider="openrouter")
    removed = ProviderModelEntry(model_id="removed", provider="openrouter")
    addition_plan = propose_additions(
        [candidate],
        {candidate.key(): ModelAdmissionStatus.CANDIDATE},
    )
    removal_plan = propose_removals(set(), [removed])

    merged = merge_patch_plans(addition_plan, removal_plan)

    assert merged.provider == "openrouter"
    assert len(merged.additions) == 1
    assert merged.removals == [removed]
