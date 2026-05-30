"""Tests for provider model catalog snapshots and deltas."""

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


def _entry(model_id: str, **kwargs) -> ProviderModelEntry:
    return ProviderModelEntry(model_id=model_id, provider=kwargs.pop("provider", "test"), **kwargs)


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
        models=[_entry("a"), _entry("b"), _entry("c")],
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
        models=[_entry("a", pricing="free", context_window=4096)],
    )

    restored = ProviderModelSnapshot.from_dict(snapshot.to_dict())
    assert restored.provider == "test"
    assert restored.source == "fixture"
    assert restored.fetched_at == 123.0
    assert restored.get("a").context_window == 4096


def test_delta_no_changes():
    old = ProviderModelSnapshot(provider="p", source="f", models=[_entry("m1", provider="p")])
    new = ProviderModelSnapshot(provider="p", source="f", models=[_entry("m1", provider="p")])

    delta = compute_delta(old, new)

    assert delta.has_changes is False
    assert [model.model_id for model in delta.unchanged] == ["m1"]
    assert delta.added == []
    assert delta.removed == []


def test_delta_added_removed_are_deterministic():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[_entry("c", provider="p"), _entry("a", provider="p")],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[_entry("b", provider="p"), _entry("d", provider="p")],
    )

    delta = compute_delta(old, new)

    assert [model.model_id for model in delta.added] == ["b", "d"]
    assert [model.model_id for model in delta.removed] == ["a", "c"]


def test_delta_changed_pricing_context_endpoint_and_probe_state():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[
            _entry(
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
            _entry(
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
        models=[_entry("m1", provider="p", capabilities=["code", "json"])],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[_entry("m1", provider="p", capabilities=["json", "code"])],
    )

    delta = compute_delta(old, new)

    assert delta.has_changes is False


def test_delta_privacy_note_change_is_detected():
    old = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[_entry("m1", provider="p", privacy_note="")],
    )
    new = ProviderModelSnapshot(
        provider="p",
        source="f",
        models=[_entry("m1", provider="p", privacy_note="prompts may be logged")],
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


from provider_automation.runner import ProbeRunner, ProbeRunnerConfig, format_batch_results


def test_probe_runner_metadata_only():
    cfg = ProbeRunnerConfig(run_completion_smoke=False)
    runner = ProbeRunner(cfg)
    models = [ProviderModelEntry(model_id="good", provider="x", endpoint_count=1)]
    results = runner.run(models)
    assert len(results) == 1
    assert results[0].final_status in (
        ModelAdmissionStatus.SANDBOX_ONLY, ModelAdmissionStatus.CANDIDATE)


def test_probe_runner_rejects_bad_metadata():
    cfg = ProbeRunnerConfig(run_completion_smoke=False)
    runner = ProbeRunner(cfg)
    models = [ProviderModelEntry(model_id="", provider="")]
    results = runner.run(models)
    assert results[0].final_status == ModelAdmissionStatus.REJECTED


def test_probe_runner_with_smoke():
    cfg = ProbeRunnerConfig(run_completion_smoke=True, run_metadata=True)
    runner = ProbeRunner(cfg)
    runner.set_smoke_callable(lambda m, msgs, mt: "Hello from smoke test")
    models = [ProviderModelEntry(model_id="good", provider="x", endpoint_count=1)]
    results = runner.run(models)
    assert results[0].final_status in (
        ModelAdmissionStatus.SANDBOX_ONLY, ModelAdmissionStatus.CANDIDATE)


def test_probe_runner_smoke_failure():
    cfg = ProbeRunnerConfig(run_completion_smoke=True, run_metadata=False)
    runner = ProbeRunner(cfg)
    runner.set_smoke_callable(lambda m, msgs, mt: "rate limit exceeded")
    models = [ProviderModelEntry(model_id="bad", provider="x")]
    results = runner.run(models)
    assert results[0].final_status == ModelAdmissionStatus.REJECTED


def test_format_batch_results():
    from provider_automation.probe import ProbeResult
    from provider_automation.runner import BatchProbeResult
    br = BatchProbeResult(
        model=ProviderModelEntry(model_id="test", provider="x"),
        results=[ProbeResult(
            model=ProviderModelEntry(model_id="test", provider="x"),
            level=ProbeLevel.METADATA_ONLY, passed=True,
            status=ModelAdmissionStatus.CANDIDATE,
        )],
        final_status=ModelAdmissionStatus.CANDIDATE,
    )
    text = format_batch_results([br])
    assert "test" in text


# M14: Impact smoke

def test_probe_runner_missing_requested_callable_goes_to_watchlist():
    cfg = ProbeRunnerConfig(run_metadata=True, run_completion_smoke=True)
    runner = ProbeRunner(cfg)
    models = [ProviderModelEntry(model_id="good", provider="x", endpoint_count=1)]

    results = runner.run(models)

    assert results[0].final_status is ModelAdmissionStatus.WATCHLIST
    assert any("callable is not configured" in r.error for r in results[0].results)


def test_probe_runner_highest_level_uses_probe_order_not_string_order():
    cfg = ProbeRunnerConfig(
        run_metadata=False,
        run_completion_smoke=True,
        run_stream_smoke=True,
    )
    runner = ProbeRunner(cfg)
    runner.set_smoke_callable(lambda m, msgs, mt: "completion ok")
    runner.set_stream_callable(lambda m, msgs, mt: ["stream ", "ok"])

    results = runner.run([ProviderModelEntry(model_id="good", provider="x")])

    assert results[0].highest_level_passed is ProbeLevel.STREAM_SMOKE


def test_format_batch_results_redacts_secret_like_model_ids_and_errors():
    from provider_automation.probe import ProbeResult
    from provider_automation.runner import BatchProbeResult
    model = ProviderModelEntry(model_id="sk-secret-model", provider="x")
    batch = BatchProbeResult(
        model=model,
        results=[ProbeResult(
            model=model,
            level=ProbeLevel.COMPLETION_SMOKE,
            passed=False,
            status=ModelAdmissionStatus.REJECTED,
            error="Bearer should not leak",
        )],
        final_status=ModelAdmissionStatus.REJECTED,
    )

    text = format_batch_results([batch])

    assert "[REDACTED]" in text
    assert "sk-secret-model" not in text
    assert "Bearer should not leak" not in text


from provider_automation.impact import check_impact, check_removal_impact, format_impact_smoke


def test_check_impact_new_free_model():
    models = [ProviderModelEntry(model_id="new_free", provider="x", pricing="free",
                                 endpoint_count=1)]
    smoke = check_impact(models, currently_routed=set())
    assert len(smoke.safe_additions) == 1
    assert smoke.safe_additions[0].model_id == "new_free"


def test_check_impact_paid_model_warns():
    models = [ProviderModelEntry(model_id="paid_model", provider="x", pricing="paid")]
    smoke = check_impact(models, currently_routed=set())
    assert len(smoke.critical) == 1
    assert any("billing" in w for w in smoke.critical[0].warnings)


def test_check_impact_privacy_watchlist():
    models = [ProviderModelEntry(model_id="suspicious", provider="x",
                                 privacy_note="prompts logged")]
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
    models = [ProviderModelEntry(model_id="safe", provider="x", pricing="free",
                                 endpoint_count=1)]
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
    models = [ProviderModelEntry(
        model_id="sk-impact",
        provider="x",
        pricing="free",
        endpoint_count=1,
        privacy_note="token=secret",
    )]
    smoke = check_impact(models, currently_routed=set())

    text = format_impact_smoke(smoke)

    assert "[REDACTED]" in text
    assert "sk-impact" not in text
    assert "token=secret" not in text


from provider_automation.review import build_review_bundle


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
    paid = _entry("paid", pricing="paid", endpoint_count=1)
    no_endpoint = _entry("no-endpoint", pricing="free", endpoint_count=0)
    clean = _entry("clean", pricing="free", endpoint_count=1)

    assert probe_metadata(missing).status is ModelAdmissionStatus.REJECTED
    assert probe_metadata(paid).status is ModelAdmissionStatus.WATCHLIST
    assert probe_metadata(paid).passed is False
    assert probe_metadata(no_endpoint).status is ModelAdmissionStatus.WATCHLIST
    assert probe_metadata(no_endpoint).passed is False
    assert probe_metadata(clean).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_metadata(clean).passed is True


def test_probe_completion_and_stream_smoke_classify_errors():
    model = _entry("m", endpoint_count=1)

    assert probe_completion_smoke("", model).status is ModelAdmissionStatus.REJECTED
    assert probe_completion_smoke("quota exceeded", model).status is ModelAdmissionStatus.REJECTED
    assert probe_completion_smoke("exact safe response", model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_stream_smoke([], model).status is ModelAdmissionStatus.REJECTED
    assert probe_stream_smoke(["safe ", "stream"], model).status is ModelAdmissionStatus.SANDBOX_ONLY


def test_probe_coding_and_quality_thresholds():
    model = _entry("m", endpoint_count=1)

    assert probe_coding_fixture(0, 0, model).status is ModelAdmissionStatus.REJECTED
    assert probe_coding_fixture(2, 4, model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_coding_fixture(4, 5, model).status is ModelAdmissionStatus.CANDIDATE
    assert probe_quality_gate(0.59, model).status is ModelAdmissionStatus.REJECTED
    assert probe_quality_gate(0.6, model).status is ModelAdmissionStatus.SANDBOX_ONLY
    assert probe_quality_gate(0.8, model).status is ModelAdmissionStatus.CANDIDATE


def test_probe_pipeline_never_accepts_routing_enabled():
    model = _entry("m")

    with pytest.raises(ValueError, match="cannot enable routing"):
        ProbeResult(
            model=model,
            level=ProbeLevel.QUALITY_GATE,
            passed=True,
            status=ModelAdmissionStatus.ROUTING_ENABLED,
        )


def test_determine_final_status_precedence():
    model = _entry("m")
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
