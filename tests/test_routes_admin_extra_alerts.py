"""Tests for routes/admin_extra_alerts.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_extra_alerts


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin_extra_alerts.router)
    return TestClient(app)


def _auth_headers():
    return {"Authorization": "Bearer admin-token"}


@pytest.fixture(autouse=True)
def _clean_rules():
    with patch.object(admin_extra_alerts, "_ALERT_RULES", {}):
        yield


def test_list_alert_rules_empty(client):
    response = client.get("/api/alerts/rules", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["rules"] == []


def test_create_alert_rule(client):
    response = client.post(
        "/api/alerts/rules",
        headers=_auth_headers(),
        json={"name": "high error rate", "metric": "error_rate", "threshold": 0.1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["rule"]["name"] == "high error rate"
    assert data["rule"]["threshold"] == 0.1


def test_create_alert_rule_missing_name(client):
    response = client.post(
        "/api/alerts/rules",
        headers=_auth_headers(),
        json={"metric": "error_rate"},
    )
    assert response.status_code == 400


def test_update_alert_rule(client):
    client.post(
        "/api/alerts/rules",
        headers=_auth_headers(),
        json={"name": "rule1"},
    )
    rule_id = admin_extra_alerts._ALERT_RULES[list(admin_extra_alerts._ALERT_RULES.keys())[0]]["rule_id"]
    response = client.put(
        f"/api/alerts/rules/{rule_id}",
        headers=_auth_headers(),
        json={"enabled": False, "threshold": 0.9, "name": "rule1 updated"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rule"]["enabled"] is False
    assert data["rule"]["threshold"] == 0.9
    assert data["rule"]["name"] == "rule1 updated"


def test_update_alert_rule_not_found(client):
    response = client.put(
        "/api/alerts/rules/missing",
        headers=_auth_headers(),
        json={"enabled": False},
    )
    assert response.status_code == 404


def test_delete_alert_rule(client):
    client.post(
        "/api/alerts/rules",
        headers=_auth_headers(),
        json={"name": "rule1"},
    )
    rule_id = admin_extra_alerts._ALERT_RULES[list(admin_extra_alerts._ALERT_RULES.keys())[0]]["rule_id"]
    response = client.delete(f"/api/alerts/rules/{rule_id}", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["rule_id"] == rule_id
    assert rule_id not in admin_extra_alerts._ALERT_RULES


def test_delete_alert_rule_not_found(client):
    response = client.delete("/api/alerts/rules/missing", headers=_auth_headers())
    assert response.status_code == 404
