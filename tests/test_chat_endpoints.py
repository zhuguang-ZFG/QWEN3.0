from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import routes.chat_endpoints as chat_endpoints
import routes.public_demo as public_demo
import server


def test_server_registers_extracted_chat_endpoints():
    paths = {
        route.path
        for route in server.app.routes
        if isinstance(route, APIRoute)
    }

    assert "/v1/chat/completions" in paths
    assert "/v1/messages" in paths
    assert "/public/demo/chat" in paths
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


def test_public_demo_chat_fails_closed(monkeypatch):
    monkeypatch.delenv("LIMA_PUBLIC_DEMO_ENABLED", raising=False)

    client = TestClient(server.app)
    response = client.post(
        "/public/demo/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "LiMa public demo is disabled."


def test_public_demo_chat_delegates_with_bounds(monkeypatch):
    captured = {}

    async def fake_handle_chat(req, **kwargs):
        captured["model"] = req.model
        captured["max_tokens"] = req.max_tokens
        captured["messages"] = [(m.role, m.content) for m in req.messages]
        captured["kwargs"] = kwargs
        return JSONResponse({"ok": True})

    monkeypatch.setenv("LIMA_PUBLIC_DEMO_ENABLED", "1")
    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)
    public_demo._public_demo_hits.clear()

    client = TestClient(server.app)
    response = client.post(
        "/public/demo/chat",
        headers={"X-Forwarded-For": "203.0.113.10"},
        json={
            "model": "lima-1.3",
            "messages": [{"role": "user", "content": "hello public demo"}],
            "stream": False,
            "max_tokens": 999,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["model"] == "lima-1.3"
    assert captured["max_tokens"] == 200
    assert captured["messages"] == [("user", "hello public demo")]
    assert captured["kwargs"]["fmt"] == "openai"
    assert captured["kwargs"]["client_ip"] == "203.0.113.10"
    assert captured["kwargs"]["ide_source"] == "public_demo"


def test_public_demo_chat_rejects_tool_requests(monkeypatch):
    monkeypatch.setenv("LIMA_PUBLIC_DEMO_ENABLED", "1")
    public_demo._public_demo_hits.clear()

    client = TestClient(server.app)
    response = client.post(
        "/public/demo/chat",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported public demo request"


def test_openai_tool_history_converts_to_anthropic_tool_blocks():
    body = {
        "model": "lima-1.3",
        "messages": [
            {"role": "user", "content": "run a tool"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": "{\"command\":\"echo ok\"}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "ok\n",
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": "Run a command",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    }

    converted = chat_endpoints._openai_to_anthropic_tool_body(body)

    assert converted["messages"] == [
        {"role": "user", "content": "run a tool"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "bash",
                    "input": {"command": "echo ok"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "ok\n",
                }
            ],
        },
    ]


def test_openai_endpoint_routes_tool_history_before_chatrequest_validation(monkeypatch):
    captured = {}

    async def fake_forward(body):
        captured["messages"] = body["messages"]
        return {
            "content": [{"type": "text", "text": "tool history accepted"}],
            "usage": {},
        }

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_anthropic_native_forward", fake_forward)

    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "lima-1.3",
            "messages": [
                {"role": "user", "content": "run a tool"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": "{\"command\":\"echo ok\"}",
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "ok\n"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "description": "Run a command",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "tool history accepted"
    assert captured["messages"][1]["content"][0]["type"] == "tool_use"
    assert captured["messages"][2]["content"][0]["type"] == "tool_result"
