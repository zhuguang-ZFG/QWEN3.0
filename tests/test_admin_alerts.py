"""Tests for alert rules CRUD endpoints (Phase 3.2)."""

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from routes.admin_api import _ALERT_RULES_PATH, router as admin_api_router
from routes.admin_auth import verify_admin, verify_csrf


@pytest.fixture(autouse=True)
def _clean_alert_rules():
    """Remove alert_rules.json before and after each test."""
    if _ALERT_RULES_PATH.exists():
        _ALERT_RULES_PATH.unlink()
    yield
    if _ALERT_RULES_PATH.exists():
        _ALERT_RULES_PATH.unlink()


app = FastAPI()
app.dependency_overrides[verify_admin] = lambda: None
app.dependency_overrides[verify_csrf] = lambda: None
app.include_router(admin_api_router, prefix="/admin")
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-admin-token"}


# -- Read / list -----------------------------------------------------------

def test_list_empty():
    resp = client.get("/admin/api/alerts/rules", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["rules"] == []


# -- Create ----------------------------------------------------------------

def test_create_rule():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "High Error Rate", "metric": "error_rate", "condition": "gt", "threshold": 0.8},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["rule"]["name"] == "High Error Rate"
    assert data["rule"]["metric"] == "error_rate"
    assert data["rule"]["condition"] == "gt"
    assert data["rule"]["threshold"] == 0.8
    assert "rule_id" in data["rule"]


def test_create_rule_appears_in_list():
    client.post(
        "/admin/api/alerts/rules",
        json={"name": "Rule A", "metric": "latency_ms", "condition": "lt", "threshold": 200},
        headers=HEADERS,
    )
    resp = client.get("/admin/api/alerts/rules", headers=HEADERS)
    assert resp.status_code == 200
    rules = resp.json()["rules"]
    assert len(rules) == 1
    assert rules[0]["name"] == "Rule A"


# -- Validation -------------------------------------------------------------

def test_create_rejects_invalid_condition():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "Bad", "condition": "inject"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_create_rejects_invalid_metric():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "Bad", "metric": "cpu_temp"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_create_rejects_non_numeric_threshold():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "Bad", "threshold": "high"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_create_rejects_small_window():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "Bad", "window_sec": 5},
        headers=HEADERS,
    )
    assert resp.status_code == 422


# -- Update ----------------------------------------------------------------

def test_update_rule():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "Original", "threshold": 0.5},
        headers=HEADERS,
    )
    rule_id = resp.json()["rule"]["rule_id"]

    resp = client.put(
        f"/admin/api/alerts/rules/{rule_id}",
        json={"threshold": 0.9, "name": "Updated"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["rule"]["threshold"] == 0.9
    assert resp.json()["rule"]["name"] == "Updated"


def test_update_nonexistent_returns_404():
    resp = client.put(
        "/admin/api/alerts/rules/nonexistent",
        json={"threshold": 0.5},
        headers=HEADERS,
    )
    assert resp.status_code == 404


# -- Delete ----------------------------------------------------------------

def test_delete_rule():
    resp = client.post(
        "/admin/api/alerts/rules",
        json={"name": "To Delete"},
        headers=HEADERS,
    )
    rule_id = resp.json()["rule"]["rule_id"]

    resp = client.delete(f"/admin/api/alerts/rules/{rule_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify list empty
    resp = client.get("/admin/api/alerts/rules", headers=HEADERS)
    assert resp.json()["rules"] == []


def test_delete_nonexistent_returns_404():
    resp = client.delete("/admin/api/alerts/rules/nonexistent", headers=HEADERS)
    assert resp.status_code == 404
