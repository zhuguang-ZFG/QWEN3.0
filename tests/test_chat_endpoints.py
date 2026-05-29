from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import routes.chat_endpoints as chat_endpoints
import server


def test_server_registers_extracted_chat_endpoints():
    paths = {
        route.path
        for route in server.app.routes
        if isinstance(route, APIRoute)
    }

    assert "/v1/chat/completions" in paths
    assert "/v1/messages" in paths
    assert server.chat_completions is chat_endpoints.chat_completions
    assert server.anthropic_messages is chat_endpoints.anthropic_messages


def test_anthropic_vision_messages_convert_base64_blocks():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "YWJj",
                    },
                },
            ],
        }
    ]

    converted = chat_endpoints._anthropic_vision_messages(messages)

    assert converted == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,YWJj"},
                },
            ],
        }
    ]


def test_openai_endpoint_delegates_to_server_handle_chat(monkeypatch):
    captured = {}

    async def fake_handle_chat(req, **kwargs):
        captured["model"] = req.model
        captured["messages"] = [(m.role, m.content) for m in req.messages]
        captured["kwargs"] = kwargs
        return JSONResponse({"ok": True})

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key", "X-Test-Header": "yes"},
        json={
            "model": "lima-1.3",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["model"] == "lima-1.3"
    assert captured["messages"] == [("user", "hello")]
    assert captured["kwargs"]["fmt"] == "openai"
    assert captured["kwargs"]["request_headers"]["x-test-header"] == "yes"
