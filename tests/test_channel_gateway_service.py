"""Tests for channel_gateway service - V1 guest experience with owner-only rejection."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-salt-for-channel-tests"

from channel_gateway.models import (
    BindingStatus,
    InboundMessage,
)
from channel_gateway.service import (
    _TIP_FOOTER,
    ChannelService,
)
from channel_gateway.store import ChannelStore


def _make_store():
    store = ChannelStore(":memory:")
    store._create_tables()
    return store


def _make_svc(store=None, enabled=True):
    if store is None:
        store = _make_store()
    return ChannelService(store=store, enabled=enabled)


_msg_counter = [0]


def _inbound(msg_id=None, sender="u1", text="hello", conv_id="c1"):
    if msg_id is None:
        _msg_counter[0] += 1
        msg_id = f"msg-{_msg_counter[0]}"
    return InboundMessage(
        message_id=msg_id,
        sender_id=sender,
        conversation_id=conv_id,
        conversation_type="private",
        text=text,
    )


class TestChannelServiceGuestLifecycle:
    def setup_method(self):
        self.store = _make_store()
        self.svc = _make_svc(store=self.store)

    def test_unbound_user_auto_guest_bind_on_hello(self):
        reply = self.svc.handle_message(_inbound(text="hello"))
        assert reply.ok is True
        assert "LiMa" in reply.reply["text"]
        assert "/menu" in reply.reply["text"]

    def test_unbound_user_gets_bind_prompt_when_auto_bind_off(self, monkeypatch):
        monkeypatch.setenv("LIMA_CHANNEL_AUTO_GUEST_BIND", "0")
        svc = _make_svc(store=self.store)
        reply = svc.handle_message(_inbound(text="hello"))
        assert reply.ok is False
        body = (reply.error or reply.reply.get("text", "")).lower()
        assert "bind" in body

    def test_unbound_user_bind_command_no_code(self):
        reply = self.svc.handle_message(_inbound(text="/bind"))
        body = (reply.error or reply.reply.get("text", "")).lower()
        assert "bind" in body or "码" in (reply.reply.get("text") or "")

    def test_bind_flow_defaults_to_guest(self):
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text=f"/bind {code}"))
        assert reply.ok is True
        assert "访客" in reply.reply["text"] or "guest" in reply.reply["text"].lower()

    def test_bound_guest_can_chat(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="hello world"))
        assert reply.ok is True
        assert "[chat] hello world" in reply.reply["text"]

    def test_guest_rejected_digest(self):
        self._bind_user("wx-guest-d")
        reply = self.svc.handle_message(_inbound(sender="wx-guest-d", text="/简报"))
        assert reply.ok is False
        body = reply.reply.get("text") or reply.error or ""
        assert "owner" in body.lower() or "主人" in body

    def test_session_reset_clears_history(self):
        from channel_gateway.chat_session import ChannelChatSession
        from channel_gateway.integrations import build_reset_handler

        sess = ChannelChatSession(self.store)
        sess.record_turn("wx-reset", "user", "one")
        assert self.store.count_chat_turns(self.store._hash_id("wx-reset")) == 1
        self._bind_user("wx-reset")
        self.svc._reset_handler = build_reset_handler(sess)
        reply = self.svc.handle_message(_inbound(sender="wx-reset", text="/reset"))
        assert reply.ok is True
        assert self.store.count_chat_turns(self.store._hash_id("wx-reset")) == 0

    def test_guest_wiki_tool_when_enabled(self, monkeypatch):
        monkeypatch.setenv("LIMA_CHANNEL_TOOLS", "1")
        from channel_gateway import channel_tools as ct_mod

        monkeypatch.setattr(
            ct_mod,
            "fetch_wiki",
            lambda q, **kw: {"ok": True, "text": f"stub-wiki:{q}"},
        )
        self._bind_user("wx-tool-1")
        reply = self.svc.handle_message(
            _inbound(sender="wx-tool-1", text="/百科 测试"),
        )
        assert reply.ok is True
        assert "stub-wiki:测试" in reply.reply["text"]

    def test_bound_guest_plain_text_routes_to_chat(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="how are you?"))
        assert reply.ok is True
        assert "[chat]" in reply.reply["text"]

    def test_duplicate_message_noop(self):
        self._bind_user("wx-user-1")
        msg = _inbound(msg_id="dup-001", sender="wx-user-1", text="hello")
        first = self.svc.handle_message(msg)
        assert first.ok is True
        second = self.svc.handle_message(msg)
        assert second.ok is False
        assert "duplicate" in (second.error or "").lower()

    def test_paused_user_cannot_chat(self):
        self._bind_user("wx-user-1")
        binding = self.store.get_binding_by_channel_user("wechat", "wx-user-1")
        self.store.set_binding_status(binding.binding_id, BindingStatus.PAUSED)
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="hello"))
        assert reply.ok is False
        body = reply.error or reply.reply.get("text", "")
        assert "paused" in body.lower() or "暂停" in body

    def test_paused_user_can_resume(self):
        self._bind_user("wx-user-1")
        binding = self.store.get_binding_by_channel_user("wechat", "wx-user-1")
        self.store.set_binding_status(binding.binding_id, BindingStatus.PAUSED)
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/resume"))
        assert reply.ok is True

    # -- Guest Commands -------------------------------------------------

    def test_code_command_guest(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/code explain async"))
        assert reply.ok is True
        assert "code help" in reply.reply["text"]

    def test_draw_command_guest(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/draw LiMa"))
        assert reply.ok is True
        assert "draw demo" in reply.reply["text"]

    def test_demo_command_guest(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/demo"))
        assert reply.ok is True
        assert "体验" in reply.reply["text"] or "Demo" in reply.reply["text"]
        assert "/menu" in reply.reply["text"]

    def test_about_command_guest(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/about"))
        assert reply.ok is True
        text = reply.reply["text"]
        assert "LiMa" in text
        assert "Hermes" in text or "不是 Hermes" in text

    def test_reset_command_guest(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/reset"))
        assert reply.ok is True
        assert "session cleared" in reply.reply["text"]

    def test_help_guest(self):
        reply = self.svc.handle_message(_inbound(text="/help"))
        assert reply.ok is True
        text = reply.reply["text"]
        assert "/menu" in text or "菜单" in text
        assert "LiMa" in text

    def test_greeting_fast_path(self):
        reply = self.svc.handle_message(_inbound(sender="wx-new-1", text="你好"))
        assert reply.ok is True
        text = reply.reply["text"]
        assert "LiMa" in text
        assert "/menu" in text
        assert _TIP_FOOTER not in text

    # -- Owner-Only Rejection -------------------------------------------

    def test_guest_rejected_code_task(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/code-task fix bug"))
        assert reply.ok is False
        body = reply.reply["text"].lower()
        assert "owner" in body or "主人" in reply.reply["text"]

    def test_guest_rejected_device(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/device write LiMa"))
        assert reply.ok is False
        body = reply.reply["text"].lower()
        assert "owner" in body or "主人" in reply.reply["text"]

    def test_guest_rejected_status(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/status"))
        assert reply.ok is False
        body = reply.reply["text"].lower()
        assert "owner" in body or "主人" in reply.reply["text"]

    def test_guest_rejected_artifact(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/artifact abc123"))
        assert reply.ok is False
        body = reply.reply["text"].lower()
        assert "owner" in body or "主人" in reply.reply["text"]

    def test_guest_rejected_memory(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/memory recent"))
        assert reply.ok is False
        body = reply.reply["text"].lower()
        assert "owner" in body or "主人" in reply.reply["text"]

    def test_owner_only_commands_dispatch_for_owner(self):
        sender = "wx-owner-1"
        owner_hash = self.store._hash_id(sender)
        os.environ["LIMA_CHANNEL_OWNER_HASHES"] = owner_hash
        try:
            self._bind_user(sender)
        finally:
            os.environ.pop("LIMA_CHANNEL_OWNER_HASHES", None)

        cases = [
            ("/code-task fix bug", "created"),
            ("/device text LiMa", "Device task"),
            ("/status", "LiMa Status"),
            ("/artifact task-1", "not found"),
            ("/memory recent", "memories"),
        ]
        for text, marker in cases:
            reply = self.svc.handle_message(_inbound(sender=sender, text=text))
            assert reply.ok is True
            assert marker in reply.reply["text"]

    def test_owner_code_task_uses_agent_task_contract(self):
        from routes.agent_tasks import _reset_for_tests, _store

        _reset_for_tests()
        sender = "wx-owner-1"
        owner_hash = self.store._hash_id(sender)
        os.environ["LIMA_CHANNEL_OWNER_HASHES"] = owner_hash
        try:
            self._bind_user(sender)
            reply = self.svc.handle_message(_inbound(sender=sender, text="/code-task fix bug"))
            assert reply.ok is True
            task_id = reply.reply["text"].split()[1]
            task = _store.get(task_id)
            assert task["request"]["task_id"] == task_id
            assert task["request"]["goal"] == "fix bug"
            assert task["events"][0]["type"] == "created"
        finally:
            os.environ.pop("LIMA_CHANNEL_OWNER_HASHES", None)
            _reset_for_tests()

    # -- State Change ---------------------------------------------------

    def test_pause_resume_flow(self):
        self._bind_user("wx-user-1")
        self.svc.handle_message(_inbound(sender="wx-user-1", text="/pause"))
        chat_reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="hello"))
        body = chat_reply.error or chat_reply.reply.get("text", "")
        assert "paused" in body.lower() or "暂停" in body
        self.svc.handle_message(_inbound(sender="wx-user-1", text="/resume"))
        chat_reply2 = self.svc.handle_message(_inbound(sender="wx-user-1", text="hello"))
        assert chat_reply2.ok is True

    def test_unbind_command(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/unbind"))
        assert reply.ok is True
        assert "解除绑定" in reply.reply["text"]

    def test_revoked_user_can_rebind(self):
        self._bind_user("wx-user-1")
        binding = self.store.get_binding_by_channel_user("wechat", "wx-user-1")
        self.store.set_binding_status(binding.binding_id, BindingStatus.REVOKED)
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text=f"/bind {code}"))
        assert reply.ok is True

    def test_kill_switch_disabled(self):
        self._bind_user("wx-user-1")
        svc = _make_svc(store=self.store, enabled=False)
        reply = svc.handle_message(_inbound(sender="wx-user-1", text="hello"))
        assert reply.ok is False
        assert "disabled" in (reply.error or "").lower()

    def test_unknown_command(self):
        self._bind_user("wx-user-1")
        reply = self.svc.handle_message(_inbound(sender="wx-user-1", text="/foobar"))
        assert reply.ok is False
        body = (reply.error or reply.reply["text"]).lower()
        assert "unknown" in body or "未识别" in reply.reply["text"]

    def _bind_user(self, sender_id):
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        self.svc.handle_message(_inbound(sender=sender_id, text=f"/bind {code}"))
