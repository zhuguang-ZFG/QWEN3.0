"""End-to-end smoke tests - zero-friction guest bind, owner-only rejection."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "smoke-test-salt-e2e"
os.environ["LIMA_CHANNEL_DB_PATH"] = ":memory:"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from channel_gateway.store import ChannelStore
from channel_gateway.service import ChannelService
from routes.channel_gateway import router, inject_deps, _reset_deps_for_test

TOKEN = "test-sidecar-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


_bind_counter = [0]

def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


def _reset():
    _reset_deps_for_test()
    os.environ["LIMA_WECHAT_SIDECAR_TOKEN"] = TOKEN
    os.environ["WECHAT_BRIDGE_ENABLED"] = "1"
    store = ChannelStore(":memory:")
    store._create_tables()
    svc = ChannelService(store=store, enabled=True)
    inject_deps(store=store, service=svc)


class TestWechatChannelSmoke:
    def setup_method(self):
        _reset()
        self.app = _make_app()
        self.client = TestClient(self.app)
        _bind_counter[0] = 0

    def _msg(self, mid, sender, text, ts=1):
        return self.client.post("/channel/v1/wechat/message", json={
            "message_id": mid,
            "sender_id": sender,
            "conversation_id": "c1",
            "conversation_type": "private",
            "text": text,
            "timestamp": ts,
        }, headers=HEADERS)

    def _bind(self, sender):
        _bind_counter[0] += 1
        r = self.client.post("/channel/v1/bind/start", json={
            "channel": "wechat", "lima_user_id": "operator",
        }, headers=HEADERS)
        code = r.json()["binding_code"]
        self._msg(f"bind-{sender}-{_bind_counter[0]}", sender, f"/bind {code}", 1)

    def test_full_bind_chat_flow_guest(self):
        self._bind("alice")
        r = self._msg("m1", "alice", "hello", 2)
        assert r.json()["ok"]
        assert "[chat]" in r.json()["reply"]["text"]

    def test_guest_commands_all_work(self):
        self._bind("bob")
        for cmd, text in [
            ("/chat hello", "chat"),
            ("/code explain async", "code help"),
            ("/draw LiMa", "draw demo"),
            ("/demo", "LiMa Demo"),
            ("/about", "LiMa"),
            ("/reset", "已清空"),
        ]:
            r = self._msg(f"cmd-{cmd[:6]}", "bob", text)
            assert r.json()["ok"], f"{cmd} should succeed for guest"

    def test_owner_only_commands_rejected_for_guest(self):
        self._bind("carol")
        for cmd in ("/status", "/device write LiMa", "/artifact abc",
                     "/code-task fix bug", "/memory recent"):
            r = self._msg(f"rej-{cmd[:8]}", "carol", cmd)
            assert not r.json()["ok"], f"{cmd} should be rejected for guest"
            assert "owner" in r.json()["reply"]["text"].lower()

    def test_pause_resume_cycle(self):
        self._bind("dave")
        self._msg("p1", "dave", "/pause", 2)
        r = self._msg("p2", "dave", "hi", 3)
        assert not r.json()["ok"]
        self._msg("p3", "dave", "/resume", 4)
        r = self._msg("p4", "dave", "hi again", 5)
        assert r.json()["ok"]

    def test_unbind_then_auto_guest_on_next_message(self):
        self._bind("eve")
        r = self._msg("u1", "eve", "/unbind", 2)
        assert r.json()["ok"]
        r = self._msg("u2", "eve", "hi", 3)
        assert r.json()["ok"]
        assert "欢迎使用" in r.json()["reply"]["text"]

    def test_scan_and_chat_without_bind_code(self):
        r = self._msg("s1", "stranger", "hello", 1)
        assert r.json()["ok"]
        assert "欢迎使用" in r.json()["reply"]["text"]

    def test_unbound_user_cannot_chat_when_auto_bind_disabled(self, monkeypatch):
        monkeypatch.setenv("LIMA_CHANNEL_AUTO_GUEST_BIND", "0")
        _reset()
        self.app = _make_app()
        self.client = TestClient(self.app)
        r = self.client.post("/channel/v1/wechat/message", json={
            "message_id": "s2",
            "sender_id": "stranger2",
            "conversation_id": "c1",
            "conversation_type": "private",
            "text": "hello",
            "timestamp": 1,
        }, headers=HEADERS)
        assert not r.json()["ok"]

    def test_health_reflects_bindings(self):
        r = self.client.get("/channel/v1/wechat/health", headers=HEADERS)
        assert r.json()["bound_users"] == 0
        self._bind("frank")
        r = self.client.get("/channel/v1/wechat/health", headers=HEADERS)
        assert r.json()["bound_users"] == 1
