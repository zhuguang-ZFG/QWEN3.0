"""Smoke test for WeChat Channel Gateway - V1 guest experience.

Usage:
    python scripts/smoke_wechat_channel_gateway.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "smoke-test-salt"
os.environ["LIMA_CHANNEL_DB_PATH"] = ":memory:"
os.environ["LIMA_WECHAT_SIDECAR_TOKEN"] = "smoke-token"
os.environ["WECHAT_BRIDGE_ENABLED"] = "1"
os.environ["LIMA_CHANNEL_TOOLS"] = "1"
os.environ["LIMA_CHANNEL_SESSION"] = "1"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from channel_gateway.store import ChannelStore
from channel_gateway.service import ChannelService
from routes.channel_gateway import router, inject_deps, _reset_deps_for_test

app = FastAPI()
app.include_router(router)
client = TestClient(app)

TOKEN = "smoke-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


_smoke_store = None


def _reset():
    global _smoke_store
    _reset_deps_for_test()
    store = ChannelStore(":memory:")
    store._create_tables()
    svc = ChannelService(store=store, enabled=True, wire_integrations=False)
    inject_deps(store=store, service=svc)
    _smoke_store = store
    return store


def main():
    store = _reset()

    def step(label):
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")

    def api(method, path, body=None):
        if method == "GET":
            return client.get(path, headers=HEADERS)
        return client.post(path, json=body, headers=HEADERS)

    # 1. Health
    step("1. Health check")
    r = api("GET", "/channel/v1/wechat/health")
    assert r.status_code == 200
    assert r.json()["enabled"]
    print(f"   OK: {r.json()}")

    # 2. Create binding code
    step("2. Create binding code")
    r = api("POST", "/channel/v1/bind/start", {"channel": "wechat", "lima_user_id": "operator"})
    assert r.status_code == 200
    code = r.json()["binding_code"]
    print(f"   code={code}")

    # 3. Bind (defaults to guest)
    step("3. Bind (guest)")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s1", "sender_id": "wx-user",
        "conversation_id": "c1", "text": f"/bind {code}", "timestamp": 1,
    })
    assert r.json()["ok"]
    assert "guest" in r.json()["reply"]["text"].lower()
    print(f"   OK: role=guest")

    # 4. Guest chat
    step("4. Guest plain chat")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s2", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "hello LiMa", "timestamp": 2,
    })
    assert r.json()["ok"]
    preview = r.json()["reply"]["text"][:80].encode("ascii", errors="replace").decode()
    print(f"   OK: {preview}")

    # 5. Guest /code
    step("5. Guest /code (explanation)")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s3", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/code explain async/await", "timestamp": 3,
    })
    assert r.json()["ok"]
    preview = r.json()["reply"]["text"][:80].encode("ascii", errors="replace").decode()
    print(f"   OK: {preview}")

    # 6. Guest /draw
    step("6. Guest /draw (demo preview)")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s4", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/draw LiMa", "timestamp": 4,
    })
    assert r.json()["ok"]
    preview = r.json()["reply"]["text"][:80].encode("ascii", errors="replace").decode()
    print(f"   OK: {preview}")

    # 7. Guest /demo
    step("7. Guest /demo")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s5", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/demo", "timestamp": 5,
    })
    assert r.json()["ok"]
    print(f"   OK: demo text received")

    # 8. Guest /about
    step("8. Guest /about")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s6", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/about", "timestamp": 6,
    })
    assert r.json()["ok"]
    print(f"   OK: about text received")

    # 9. Owner-only rejection: /status
    step("9. Guest rejected: /status")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s7", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/status", "timestamp": 7,
    })
    assert not r.json()["ok"]
    assert "owner" in r.json()["reply"]["text"].lower()
    print(f"   OK: rejected with owner-only message")

    # 10. Owner-only rejection: /device
    step("10. Guest rejected: /device")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s8", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/device write LiMa", "timestamp": 8,
    })
    assert not r.json()["ok"]
    print(f"   OK: rejected")

    # 11. Owner-only rejection: /artifact
    step("11. Guest rejected: /artifact")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s9", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/artifact abc123", "timestamp": 9,
    })
    assert not r.json()["ok"]
    print(f"   OK: rejected")

    # 12. Duplicate message
    step("12. Duplicate message dedupe")
    dup = {
        "message_id": "dup-smoke", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "test", "timestamp": 10,
    }
    r1 = api("POST", "/channel/v1/wechat/message", dup)
    r2 = api("POST", "/channel/v1/wechat/message", dup)
    assert r1.json()["ok"]
    assert not r2.json()["ok"]
    print(f"   First ok={r1.json()['ok']}, Second ok={r2.json()['ok']} (should be False)")

    # 13. Pause/resume
    step("13. Pause/resume flow")
    api("POST", "/channel/v1/wechat/message", {
        "message_id": "s10", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/pause", "timestamp": 11,
    })
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s11", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "blocked?", "timestamp": 12,
    })
    assert not r.json()["ok"]
    api("POST", "/channel/v1/wechat/message", {
        "message_id": "s12", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "/resume", "timestamp": 13,
    })
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s13", "sender_id": "wx-user",
        "conversation_id": "c1", "text": "resumed chat", "timestamp": 14,
    })
    assert r.json()["ok"]
    print(f"   Pause/resume cycle OK")

    # 14. Final health
    step("14. Final health")
    r = api("GET", "/channel/v1/wechat/health")
    assert r.json()["bound_users"] >= 1
    print(f"   OK: bound_users={r.json()['bound_users']}, recent_messages={r.json()['recent_messages']}")

    # 15. Zero-friction auto guest + tools
    step("15. Auto guest + /menu (tools on)")
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s14", "sender_id": "stranger-smoke",
        "conversation_id": "c2", "text": "你好", "timestamp": 20,
    })
    assert r.json()["ok"]
    r = api("POST", "/channel/v1/wechat/message", {
        "message_id": "s15", "sender_id": "stranger-smoke",
        "conversation_id": "c2", "text": "/menu", "timestamp": 21,
    })
    assert r.json()["ok"]
    assert "/百科" in r.json()["reply"]["text"]
    print("   OK: auto guest + menu")

    # 16. Local calc (no network)
    step("16. /calc local")
    from channel_gateway.channel_tools import run_channel_tool

    calc_text = run_channel_tool(store, "calc", "2+2", channel_user_id_raw="stranger-smoke", role="guest")
    assert "4" in calc_text
    print(f"   OK: {calc_text}")

    # 17. Session store
    step("17. Chat session turns")
    from channel_gateway.chat_session import ChannelChatSession

    sess = ChannelChatSession(store)
    sess.record_turn("sess-u", "user", "a")
    sess.record_turn("sess-u", "assistant", "b")
    assert len(sess.get_messages("sess-u")) == 2
    sess.clear("sess-u")
    assert len(sess.get_messages("sess-u")) == 0
    print("   OK: session round-trip")

    print(f"\n{'=' * 60}")
    print("  GUEST SMOKE PASSED (incl. CQ-090 tools/session)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
