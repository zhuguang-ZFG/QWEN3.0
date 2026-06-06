"""Tests for channel_gateway FastAPI routes - V1 guest experience."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-salt-for-channel-tests"
os.environ["LIMA_CHANNEL_DB_PATH"] = ":memory:"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from channel_gateway.service import ChannelService
from channel_gateway.store import ChannelStore
from routes.channel_gateway import (
    _reset_deps_for_test,
    inject_deps,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)

SIDECAR_TOKEN = "test-sidecar-token"
SIDECAR_HEADERS = {"Authorization": f"Bearer {SIDECAR_TOKEN}"}


def _reset():
    os.environ["LIMA_WECHAT_SIDECAR_TOKEN"] = SIDECAR_TOKEN
    os.environ["WECHAT_BRIDGE_ENABLED"] = "1"
    store = ChannelStore(":memory:")
    store._create_tables()
    svc = ChannelService(store=store, enabled=True)
    inject_deps(store=store, service=svc)
    _reset_deps_for_test()


class TestChannelRoutes:
    def setup_method(self):
        _reset()

    def test_bind_start_success(self):
        resp = client.post("/channel/v1/bind/start", json={
            "channel": "wechat",
            "lima_user_id": "operator",
        }, headers=SIDECAR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "binding_code" in data
        assert len(data["binding_code"]) == 6

    def test_bind_start_unauthorized(self):
        resp = client.post("/channel/v1/bind/start", json={
            "channel": "wechat",
            "lima_user_id": "operator",
        }, headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_bind_start_rejects_raw_token_without_bearer(self):
        resp = client.post("/channel/v1/bind/start", json={
            "channel": "wechat",
            "lima_user_id": "operator",
        }, headers={"Authorization": SIDECAR_TOKEN})
        assert resp.status_code == 401

    def test_bind_start_requires_id_salt(self):
        old = os.environ.pop("LIMA_CHANNEL_ID_SALT", None)
        _reset_deps_for_test()
        try:
            resp = client.post("/channel/v1/bind/start", json={
                "channel": "wechat",
                "lima_user_id": "operator",
            }, headers=SIDECAR_HEADERS)
            assert resp.status_code == 503
        finally:
            if old is not None:
                os.environ["LIMA_CHANNEL_ID_SALT"] = old
            _reset_deps_for_test()

    def test_wechat_message_auto_guest_without_bind_code(self):
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-1",
            "sender_id": "test-user",
            "conversation_id": "conv-1",
            "conversation_type": "private",
            "text": "hello",
            "timestamp": 1770000000,
        }, headers=SIDECAR_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert "你好，我是 LiMa" in resp.json()["reply"]["text"]

    def test_wechat_message_duplicate(self):
        msg = {
            "message_id": "wx-dup",
            "sender_id": "test-user",
            "conversation_id": "conv-1",
            "conversation_type": "private",
            "text": "hello",
            "timestamp": 1770000000,
        }
        first = client.post("/channel/v1/wechat/message", json=msg, headers=SIDECAR_HEADERS)
        first = client.post("/channel/v1/wechat/message", json=msg, headers=SIDECAR_HEADERS)
        assert first.json()["ok"] is False

    def test_health_endpoint(self):
        resp = client.get("/channel/v1/wechat/health", headers=SIDECAR_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    def test_health_unauthorized(self):
        resp = client.get("/channel/v1/wechat/health")
        assert resp.status_code == 401

    def test_kill_switch_disabled(self):
        os.environ["WECHAT_BRIDGE_ENABLED"] = "0"
        _reset_deps_for_test()

        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-ks",
            "sender_id": "u1",
            "conversation_id": "c1",
            "text": "hi",
            "timestamp": 0,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is False

    def test_bind_flow_end_to_end_guest(self):
        # 1. Create binding code
        resp = client.post("/channel/v1/bind/start", json={
            "channel": "wechat", "lima_user_id": "operator",
        }, headers=SIDECAR_HEADERS)
        code = resp.json()["binding_code"]

        # 2. Bind (defaults to guest)
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-bind-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "conversation_type": "private",
            "text": f"/bind {code}",
            "timestamp": 1,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is True
        assert "访客" in resp.json()["reply"]["text"]

        # 3. Guest chat (plain text)
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-chat-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "text": "hello LiMa",
            "timestamp": 2,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is True

        # 4. Guest /code
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-code-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "text": "/code explain async",
            "timestamp": 3,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is True

        # 5. Guest /draw
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-draw-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "text": "/draw LiMa",
            "timestamp": 4,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is True

        # 6. Guest rejected for /status
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-status-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "text": "/status",
            "timestamp": 5,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is False
        assert "主人" in resp.json()["reply"]["text"]

        # 7. Guest rejected for /device
        resp = client.post("/channel/v1/wechat/message", json={
            "message_id": "wx-dev-1",
            "sender_id": "real-wx-user",
            "conversation_id": "conv-1",
            "text": "/device write LiMa",
            "timestamp": 6,
        }, headers=SIDECAR_HEADERS)
        assert resp.json()["ok"] is False
        assert "主人" in resp.json()["reply"]["text"]

        # 8. Health shows 1 bound
        resp = client.get("/channel/v1/wechat/health", headers=SIDECAR_HEADERS)
        assert resp.json()["bound_users"] == 1
