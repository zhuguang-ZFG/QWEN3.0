"""Tests for device WebSocket ticket exchange."""

import device_ws_ticket
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.device_gateway import router
from routes.device_gateway_helpers import _reset_for_tests
from routes.device_gateway_dispatch import extract_ws_token, ticket_device_id


class _FakeWebSocket:
    def __init__(self, query=None):
        from starlette.datastructures import Headers, QueryParams

        self.headers = Headers({})
        self.query_params = QueryParams(query or {})
        self.scope = {"state": {}}


def _gateway_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-a=secret-token,dev-1=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    device_ws_ticket.reset()
    _reset_for_tests()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_device_ws_ticket_single_use(monkeypatch):
    device_ws_ticket.reset()
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-a=secret-token")
    ticket = device_ws_ticket.issue("dev-a", "secret-token")
    assert device_ws_ticket.consume(ticket) == ("dev-a", "secret-token")
    assert device_ws_ticket.consume(ticket) is None


def test_extract_ws_token_accepts_ticket(monkeypatch):
    device_ws_ticket.reset()
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-a=secret-token")
    ticket = device_ws_ticket.issue("dev-a", "secret-token")
    ws = _FakeWebSocket(query={"ticket": ticket})
    assert extract_ws_token(ws) == "secret-token"
    assert ticket_device_id(ws) == "dev-a"


def test_create_device_ws_ticket_endpoint(monkeypatch):
    client = _gateway_client(monkeypatch)
    response = client.post(
        "/device/v1/ws/ticket",
        json={"device_id": "dev-1", "token": "test-device-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == device_ws_ticket.TTL_SECONDS
    assert device_ws_ticket.consume(body["ticket"]) == ("dev-1", "test-device-token")


def test_create_device_ws_ticket_accepts_bearer_header(monkeypatch):
    client = _gateway_client(monkeypatch)
    response = client.post(
        "/device/v1/ws/ticket",
        headers={"Authorization": "Bearer test-device-token"},
        json={"device_id": "dev-1"},
    )
    assert response.status_code == 200
    ticket = response.json()["ticket"]
    assert device_ws_ticket.consume(ticket) == ("dev-1", "test-device-token")


def test_create_device_ws_ticket_rejects_invalid(monkeypatch):
    client = _gateway_client(monkeypatch)
    response = client.post(
        "/device/v1/ws/ticket",
        json={"device_id": "dev-1", "token": "wrong-token"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "E_UNAUTHORIZED_DEVICE"


def test_extract_ws_token_rejects_query_token_by_default(monkeypatch):
    """AUDIT-11-W2：默认拒绝 query token，防止 Bearer 进入 access log/Referer。"""
    monkeypatch.delenv("LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN", raising=False)
    ws = _FakeWebSocket(query={"token": "secret-token"})
    assert extract_ws_token(ws) == ""


def test_extract_ws_token_rejects_query_authorization_by_default(monkeypatch):
    monkeypatch.delenv("LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN", raising=False)
    ws = _FakeWebSocket(query={"authorization": "Bearer secret-token"})
    assert extract_ws_token(ws) == ""


def test_extract_ws_token_allows_query_token_with_env_flag(monkeypatch):
    """Legacy 兼容：显式设置 LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN=1 时恢复 query token。"""
    monkeypatch.setenv("LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN", "1")
    ws = _FakeWebSocket(query={"token": "secret-token"})
    assert extract_ws_token(ws) == "secret-token"
