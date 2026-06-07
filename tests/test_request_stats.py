import logging

from fastapi.testclient import TestClient

import routes.request_tracking as request_tracking
import server


def test_elapsed_ms_clamps_and_reports_real_duration(monkeypatch):
    monkeypatch.setattr(server.time, "time", lambda: 12.5)
    assert server._elapsed_ms(10.0) == 2500

    monkeypatch.setattr(server.time, "time", lambda: 9.0)
    assert server._elapsed_ms(10.0) == 0


def test_record_request_looks_up_country_before_stats_lock(monkeypatch):
    observed_locks = []

    def record_location(_ip):
        observed_locks.append(server._stats_lock.locked())
        return "test-country"

    monkeypatch.setattr(request_tracking, "get_ip_location", record_location)
    monkeypatch.setattr(
        request_tracking,
        "_stats",
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
        },
    )

    server._record_request(
        "query",
        "backend",
        "chat",
        7,
        client_ip="203.0.113.7",
    )

    assert observed_locks == [False]
    assert request_tracking._stats["recent_logs"][-1]["country"] == "test-country"


def test_record_request_fans_out_via_admin_sse(monkeypatch, caplog):
    import routes.admin_sse as admin_sse

    scheduled = []

    class FakeLoop:
        def is_running(self):
            return True

        def create_task(self, coro):
            scheduled.append(coro)
            coro.close()

    async def fake_publish_log_event(_event):
        return None

    monkeypatch.setattr(request_tracking, "get_ip_location", lambda _ip: "")
    monkeypatch.setattr(admin_sse, "_main_sse_loop", FakeLoop())
    monkeypatch.setattr(admin_sse, "publish_log_event", fake_publish_log_event)
    monkeypatch.setattr(
        request_tracking,
        "_stats",
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
        },
    )

    with caplog.at_level(logging.WARNING):
        request_tracking.record_request("query", "backend", "chat", 7)

    assert scheduled
    assert "Failed to fan-out SSE log event" not in caplog.text


def test_anthropic_vision_records_real_duration(monkeypatch):
    captured = {}

    async def fake_vision_route(messages, max_tokens=4096, ide="unknown"):
        assert messages[0]["content"][1]["type"] == "image_url"
        return {"answer": "vision answer", "backend": "vision_fake"}

    def fake_elapsed_ms(started_at):
        captured["started_at"] = started_at
        return 250

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
    monkeypatch.setattr(server, "_elapsed_ms", fake_elapsed_ms)
    monkeypatch.setattr(server, "_record_request", fake_record_request)

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
    assert isinstance(captured["started_at"], float)
    assert captured["query"] == "describe this"
    assert captured["backend"] == "vision_fake"
    assert captured["intent"] == "vision"
    assert captured["duration_ms"] == 250
    assert captured["success"] is True
    assert captured["client_ip"] == "testclient"
    assert captured["ide_source"] == ""
    assert captured["sys_prompt_preview"] == ""
