"""Tool-forward Tier1 failure recording."""

import routes.tool_forward as tool_forward


def test_tier1_sync_records_failure_on_backend_error(monkeypatch):
    import health_tracker

    calls: list[tuple] = []

    monkeypatch.setattr(tool_forward, "TOOL_TIER1_BACKENDS", ["github_gpt4o_mini"])
    monkeypatch.setattr(
        tool_forward,
        "iter_tool_backends",
        lambda tier: iter(["github_gpt4o_mini"]),
    )

    from backends import BACKENDS
    from http_caller import BackendError

    monkeypatch.setitem(
        BACKENDS,
        "github_gpt4o_mini",
        {
            "url": "https://example.test/v1/chat/completions",
            "key": "k",
            "model": "gpt-4o-mini",
            "fmt": "openai",
            "auth": "bearer",
        },
    )
    monkeypatch.setattr(
        health_tracker,
        "record_failure",
        lambda name, error_code=None: calls.append((name, error_code)),
    )
    monkeypatch.setattr(health_tracker, "record_success", lambda *a, **k: None)
    monkeypatch.setattr(
        tool_forward,
        "pick_tool_backend",
        lambda tier: None,
    )
    monkeypatch.setattr(
        "http_caller.call_raw",
        lambda *a, **k: (_ for _ in ()).throw(BackendError("boom", status_code=503)),
    )

    body = {
        "messages": [{"role": "user", "content": "ping"}],
        "tools": [
            {
                "name": "Read",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
    }
    result = tool_forward.anthropic_native_forward_sync(body)

    assert result["type"] == "error"
    assert calls == [("github_gpt4o_mini", 503)]
