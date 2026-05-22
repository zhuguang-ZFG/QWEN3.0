import inspect
import time

from fastapi.testclient import TestClient

import server


def test_elapsed_ms_clamps_and_reports_real_duration(monkeypatch):
    monkeypatch.setattr(server.time, "time", lambda: 12.5)
    assert server._elapsed_ms(10.0) == 2500

    monkeypatch.setattr(server.time, "time", lambda: 9.0)
    assert server._elapsed_ms(10.0) == 0


def test_anthropic_vision_records_real_duration(monkeypatch):
    captured = {}
    server_times = iter([100.0, 100.25])
    real_time = time.time

    async def fake_vision_route(messages, max_tokens=4096, ide="unknown"):
        assert messages[0]["content"][1]["type"] == "image_url"
        return {"answer": "vision answer", "backend": "vision_fake"}

    def fake_record_request(
        query,
        backend,
        intent,
        duration_ms,
        success=True,
        **kwargs,
    ):
        captured.update(
            {
                "query": query,
                "backend": backend,
                "intent": intent,
                "duration_ms": duration_ms,
                "success": success,
                **kwargs,
            }
        )

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_vision_route", fake_vision_route)
    monkeypatch.setattr(server, "_record_request", fake_record_request)

    def fake_time():
        for frame in inspect.stack():
            if frame.filename.endswith("server.py") and frame.function in {
                "_elapsed_ms",
                "anthropic_messages",
            }:
                return next(server_times)
        return real_time()

    monkeypatch.setattr(server.time, "time", fake_time)

    client = TestClient(server.app)
    response = client.post(
        "/v1/messages",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "claude-test",
            "max_tokens": 128,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe this"},
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
            ],
        },
    )

    assert response.status_code == 200
    assert "vision answer" in response.text
    assert captured["backend"] == "vision_fake"
    assert captured["intent"] == "vision"
    assert captured["duration_ms"] > 0
    assert captured["duration_ms"] != 0
