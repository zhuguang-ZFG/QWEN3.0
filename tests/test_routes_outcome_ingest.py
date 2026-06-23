"""Tests for routes/outcome_ingest.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import outcome_ingest as oi


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(oi.router)
    return TestClient(app)


@patch.object(oi, "check_ip_limit", return_value=None)
@patch("session_memory.outcome_ledger.record", return_value="evt-1")
def test_ingest_valid_outcome(mock_record, mock_limit, client):
    response = client.post(
        "/internal/v1/outcome",
        headers={"Authorization": "Bearer test-key"},
        json={"source": "ci", "event_type": "workflow_run", "outcome": "success"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["event_id"] == "evt-1"


@patch.object(oi, "check_ip_limit", return_value=None)
def test_ingest_missing_fields(mock_limit, client):
    response = client.post(
        "/internal/v1/outcome",
        headers={"Authorization": "Bearer test-key"},
        json={"source": "ci"},
    )
    assert response.status_code == 400


@patch.object(oi, "check_ip_limit", return_value=None)
@patch("session_memory.outcome_ledger.record", side_effect=RuntimeError("db down"))
def test_ingest_record_failure(mock_record, mock_limit, client):
    response = client.post(
        "/internal/v1/outcome",
        headers={"Authorization": "Bearer test-key"},
        json={"source": "ci", "event_type": "workflow_run"},
    )
    assert response.status_code == 500
