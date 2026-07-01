from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.device_gateway import router
from routes.device_gateway_helpers import _reset_for_tests


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    _reset_for_tests()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_websocket_malformed_json_returns_protocol_error(monkeypatch):
    client = _client(monkeypatch)
    with client.websocket_connect("/device/v1/ws", headers={"Authorization": "Bearer test-device-token"}) as ws:
        ws.send_text("{not-json")
        error = ws.receive_json()

    assert error == {
        "type": "error",
        "code": "E_INVALID_JSON",
        "message": "text frame must contain a JSON object",
        "request_id": None,
    }
