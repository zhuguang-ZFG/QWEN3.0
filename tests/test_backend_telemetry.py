from observability.backend_telemetry import (
    backend_telemetry_summary,
    classify_error,
    record_backend_attempt,
)


def test_classify_error_maps_operator_relevant_failures():
    assert classify_error(status_code=402) == "quota"
    assert classify_error(status_code=429) == "rate_limit"
    assert classify_error(status_code=504) == "timeout"
    assert classify_error(error="upstream provider exploded") == "provider_5xx"
    assert classify_error(response_empty=True) == "empty_response"


def test_backend_telemetry_summary_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    assert record_backend_attempt(
        backend="github_gpt4o_mini",
        scenario="coding",
        request_type="tool_use",
        success=False,
        latency_ms=91000,
        tools_requested=True,
        status_code=403,
        error="Bearer sk-test-secret should not leak",
        phase="tool_forward",
        attempt="tier1_openai",
        model="gpt-4o-mini",
    )
    assert record_backend_attempt(
        backend="github_gpt4o_mini",
        scenario="coding",
        request_type="tool_use",
        success=True,
        latency_ms=120,
        tools_requested=True,
    )

    summary = backend_telemetry_summary(limit=10, slow_ms=30000)

    assert summary["total_recent"] == 2
    assert summary["failed_recent"] == 1
    assert summary["slow_recent"] == 1
    assert summary["error_classes"] == {"auth": 1}
    backend = summary["by_backend"]["github_gpt4o_mini"]
    assert backend["attempts"] == 2
    assert backend["success"] == 1
    assert backend["failures"] == 1
    assert "sk-test-secret" not in str(summary)
    assert "Bearer" not in str(summary)


def test_speculative_call_records_backend_attempt(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

    import speculative

    monkeypatch.setattr(speculative.health_tracker, "record_success", lambda *a, **k: None)
    monkeypatch.setattr(speculative.budget_manager, "record_usage", lambda *a, **k: None)

    def fake_call(backend: str, _messages: list[dict], _max_tokens: int) -> str:
        return f"{backend} returned enough content"

    backend, answer, _latency = speculative.speculative_call(
        ["fast_backend"],
        fake_call,
        [{"role": "user", "content": "hi"}],
        scenario="coding",
        request_type="ide",
    )

    summary = backend_telemetry_summary(limit=10)
    assert backend == "fast_backend"
    assert "enough content" in answer
    assert summary["total_recent"] == 1
    assert summary["by_backend"]["fast_backend"]["success"] == 1
    assert summary["recent"][0]["phase"] == "speculative"
    assert summary["recent"][0]["scenario"] == "coding"
