"""Tests for router_http (CQ-014 slice 7)."""

import json

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


def test_call_api_uses_build_request_body(monkeypatch):
    calls = []

    def fake_build_request_body(name, msgs, mt=1024, ide="unknown", stream=False):
        calls.append((name, stream))
        return b"{}", {"Content-Type": "application/json"}, "openai", 30

    def fake_urlopen(request, timeout=60):
        class Resp:
            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "ok"}}]}
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp()

    monkeypatch.setattr(router_http, "build_request_body", fake_build_request_body)
    monkeypatch.setattr(router_http, "cb_allow", lambda _name: True)
    monkeypatch.setattr(router_http, "cb_record", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(router_http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setitem(
        router_http.BACKENDS,
        "sync_body_backend",
        {"key": "k", "fmt": "openai", "url": "https://example.test", "model": "x"},
    )

    result = router_http.call_api(
        "sync_body_backend",
        [{"role": "user", "content": "hello"}],
    )
    assert calls == [("sync_body_backend", False)]
    assert result == "ok"


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
