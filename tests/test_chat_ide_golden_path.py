"""Chat/IDE golden path — auth, route, closeout, capability evidence (M2)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from chat_models import ChatRequest, Message


@pytest.fixture
def evidence_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test_outcome.db"
        monkeypatch.setenv("LIMA_OUTCOME_DB", str(p))
        yield p


def test_chat_golden_path_records_capability_evidence(evidence_db, monkeypatch):
    import routes.chat_handler as chat_handler
    import server

    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.setattr(server.smart_router, "detect_image_intent", lambda query: (False, ""))
    monkeypatch.setattr(server.smart_router, "detect_thinking_intent", lambda query: False)
    monkeypatch.setattr(
        server.smart_router,
        "analyze",
        lambda query, system_prompt="", ide="": {"intent": "chat", "complexity": 0.1},
    )
    monkeypatch.setattr(chat_handler, "needs_orchestration", lambda query, intent: False)
    monkeypatch.setattr(
        chat_handler,
        "v3_route",
        lambda query, messages, system_prompt="", ide="", max_tokens=4096: {
            "answer": "golden_path_ok",
            "backend": "test_backend",
            "total_ms": 12,
            "fallback_used": False,
        },
    )
    monkeypatch.setattr(chat_handler, "quality_check", lambda *args, **kwargs: True)
    monkeypatch.setattr(chat_handler, "_record_request", lambda *args, **kwargs: None)

    req = ChatRequest(
        messages=[Message(role="user", content="Return exactly: golden_path_ok")],
        max_tokens=64,
    )
    response = asyncio.run(
        server._handle_chat(
            req,
            fmt="openai",
            client_ip="127.0.0.1",
            ide_source="cursor",
            sys_prompt_preview="base",
            request_headers={"user-agent": "cursor"},
        )
    )
    data = json.loads(response.body.decode("utf-8"))
    assert data["choices"][0]["message"]["content"] == "golden_path_ok"
    # Check evidence via API instead of file
    from observability.capability_evidence import recent_evidence

    rows = recent_evidence(limit=5)
    chat_rows = [r for r in rows if r.get("loop") == "chat_ide"]
    assert chat_rows, "expected chat_ide capability evidence"
    row = chat_rows[-1]
    assert row["selected_backend"] == "test_backend"
    assert row["entrypoint"] == "/v1/chat/completions"
    assert row["status"] == "ok"
    assert "chat_post_closeout" in row.get("evidence", [])


def test_chat_endpoint_requires_private_auth(evidence_db, monkeypatch):
    from fastapi.testclient import TestClient

    import server

    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong"},
        json={
            "model": "lima-1.3",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 401
