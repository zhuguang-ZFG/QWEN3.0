"""Chat/IDE golden path — auth, route, closeout, capability evidence (M2)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def evidence_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test_outcome.db"
        monkeypatch.setenv("LIMA_OUTCOME_DB", str(p))
        yield p


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
