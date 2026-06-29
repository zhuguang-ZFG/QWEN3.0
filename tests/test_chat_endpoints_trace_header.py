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
    assert "X-LiMa-Prompt-Version" in response.headers


def test_chat_completions_includes_prompt_version_header_without_trace(monkeypatch):
    """AUDIT-3-P5：版本标记通过 response header 返回，不依赖 tracing 开启。"""
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_TRACING_ENABLED", "0")

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
    assert "X-LiMa-Prompt-Version" in response.headers
    assert "lima-prompts-v2.0" in response.headers["X-LiMa-Prompt-Version"]
