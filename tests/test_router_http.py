"""Tests for router_http (CQ-014 slice 7)."""

import router_http
from router_circuit_breaker import reset_for_tests


def setup_function():
    reset_for_tests()


def test_call_api_blocked_by_circuit_breaker():
    import router_circuit_breaker as cb

    for _ in range(cb.CB_FAILURE_THRESHOLD):
        cb.cb_record("blocked_backend", success=False)

    result = router_http.call_api("blocked_backend", [{"role": "user", "content": "hi"}])
    assert result is None


def test_build_request_body_openai_stream_flag():
    payload, headers, fmt, timeout = router_http._build_request_body(
        "nvidia_phi4",
        [{"role": "user", "content": "hello"}],
        stream=True,
    )
    assert payload is not None
    assert fmt == "openai"
    assert timeout >= 1
    body = __import__("json").loads(payload.decode())
    assert body["stream"] is True
    assert headers["Authorization"].startswith("Bearer ")


def test_call_api_stream_yields_error_when_no_key(monkeypatch):
    monkeypatch.setitem(
        router_http.BACKENDS,
        "missing_key_backend",
        {"key": "", "fmt": "openai", "url": "https://example.test", "model": "x"},
    )
    chunks = list(
        router_http.call_api_stream(
            "missing_key_backend",
            [{"role": "user", "content": "hello"}],
        )
    )
    assert chunks
    assert "[ERR]" in chunks[0]
