"""Provider automation probe runner tests."""

from provider_automation.catalog import ModelAdmissionStatus, ProviderModelEntry
from provider_automation.probe import ProbeLevel
from provider_automation.runner import ProbeRunner, ProbeRunnerConfig, format_batch_results

from provider_automation_helpers import entry

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
