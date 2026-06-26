from fastapi.testclient import TestClient

import server


def test_chat_completions_includes_trace_header(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")

    async def fake_handle_chat(req, **kwargs):
        from fastapi.responses import JSONResponse

        return JSONResponse({"ok": True})

    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "lima-1.3", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert "X-LiMa-Trace-Id" in response.headers
    assert len(response.headers["X-LiMa-Trace-Id"]) == 12
