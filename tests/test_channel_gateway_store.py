"""Tests for channel_gateway models and SQLite store - V1 with guest/owner roles."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-salt-for-channel-tests"
os.environ["LIMA_CHANNEL_DB_PATH"] = ":memory:"

from channel_gateway.models import (
    BindingRole,
    BindingStatus,
    ChannelBinding,
    ChannelBindingCode,
    ChannelMessage,
    InboundMessage,
    OutboundReply,
    CommandResult,
)
from channel_gateway.store import ChannelStore


class TestChannelModels:
    def test_binding_status_enum(self):
        assert BindingStatus.PENDING == "pending"
        assert BindingStatus.ACTIVE == "active"
        assert BindingStatus.PAUSED == "paused"
        assert BindingStatus.REVOKED == "revoked"

    def test_binding_role_enum(self):
        assert BindingRole.GUEST == "guest"
        assert BindingRole.OWNER == "owner"

    def test_channel_binding_defaults_to_guest(self):
        b = ChannelBinding(
            binding_id="bind_001",
            channel="wechat",
            channel_user_id_hash="abc123",
            display_name="Test User",
            lima_user_id="operator",
        )
        assert b.role == BindingRole.GUEST
        assert b.status == BindingStatus.PENDING

    def test_channel_binding_code_defaults(self):
        c = ChannelBindingCode(
            code_hash="hash123",
            lima_user_id="owner",
            expires_at=int(time.time()) + 300,
        )
        assert c.used_at is None
        assert c.created_at > 0

    def test_channel_message_defaults(self):
        m = ChannelMessage(
            message_id="msg_001",
            channel="wechat",
            channel_user_id_hash="user_hash",
            conversation_id_hash="conv_hash",
            direction="inbound",
            intent="chat",
            summary="hello",
        )
        assert m.task_id is None
        assert m.device_id is None
        assert m.created_at > 0

    def test_inbound_message_parsing(self):
        msg = InboundMessage(
            message_id="wx-msg-1",
            sender_id="raw-user-123",
            conversation_id="raw-conv-456",
            conversation_type="private",
            text="/chat hello world",
            timestamp=1770000000,
        )
        assert msg.message_id == "wx-msg-1"
        assert msg.sender_id == "raw-user-123"

    def test_outbound_reply(self):
        reply = OutboundReply(ok=True, reply={"text": "hello back"})
        assert reply.ok is True
        assert reply.reply["text"] == "hello back"


class TestChannelStore:
    def setup_method(self):
        self.store = ChannelStore(":memory:")
        self.store._create_tables()

    def test_create_binding_code(self):
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        assert len(code) == 6
        assert code.isdigit()

    def test_validate_binding_code_success(self):
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        assert self.store.validate_binding_code(code) is True

    def test_validate_binding_code_not_found(self):
        assert self.store.validate_binding_code("000000") is False

    def test_validate_binding_code_expired(self):
        code = self.store.create_binding_code("operator", ttl_seconds=-1)
        time.sleep(0.01)
        assert self.store.validate_binding_code(code) is False

    def test_validate_binding_code_one_time_use(self):
        code = self.store.create_binding_code("operator", ttl_seconds=300)
        assert self.store.validate_binding_code(code) is True
        assert self.store.validate_binding_code(code) is False

    def test_create_binding_defaults_to_guest(self):
        ok = self.store.create_binding("bind_001", "wechat", "raw-user-123", "Alice", "operator")
        assert ok is True
        binding = self.store.get_binding_by_channel_user("wechat", "raw-user-123")
        assert binding.role == BindingRole.GUEST

    def test_create_binding_duplicate_id(self):
        self.store.create_binding("bind_001", "wechat", "raw-1", "Alice", "operator")
        ok = self.store.create_binding("bind_001", "wechat", "raw-2", "Bob", "operator2")
        assert ok is False

    def test_get_binding_by_channel_user(self):
        self.store.create_binding("bind_001", "wechat", "raw-user-123", "Alice", "operator")
        binding = self.store.get_binding_by_channel_user("wechat", "raw-user-123")
        assert binding is not None
        assert binding.display_name == "Alice"
        assert binding.status == BindingStatus.ACTIVE
        assert binding.role == BindingRole.GUEST

    def test_get_binding_not_found(self):
        assert self.store.get_binding_by_channel_user("wechat", "nobody") is None

    def test_set_binding_status(self):
        self.store.create_binding("bind_001", "wechat", "raw-user-123", "Alice", "operator")
        assert self.store.set_binding_status("bind_001", BindingStatus.PAUSED) is True
        binding = self.store.get_binding_by_channel_user("wechat", "raw-user-123")
        assert binding.status == BindingStatus.PAUSED

    def test_set_binding_status_not_found(self):
        assert self.store.set_binding_status("nonexistent", BindingStatus.PAUSED) is False

    def test_record_message_dedupe(self):
        first = self.store.record_message("msg_001", "wechat", "raw-1", "conv-1", "inbound", "chat", "hello")
        assert first is True
        second = self.store.record_message("msg_001", "wechat", "raw-1", "conv-1", "inbound", "chat", "hello again")
        assert second is False

    def test_record_message_different_ids(self):
        assert self.store.record_message("msg_001", "wechat", "raw-1", "conv-1", "inbound", "chat", "hi")
        assert self.store.record_message("msg_002", "wechat", "raw-1", "conv-1", "inbound", "chat", "hi again")

    def test_get_binding_count(self):
        assert self.store.get_binding_count() == 0
        self.store.create_binding("bind_001", "wechat", "raw-1", "Alice", "operator")
        assert self.store.get_binding_count() == 1

    def test_get_recent_message_count(self):
        self.store.record_message("m1", "wechat", "u1", "c1", "inbound", "chat", "hi")
        self.store.record_message("m2", "wechat", "u1", "c1", "outbound", "chat", "resp")
        assert self.store.get_recent_message_count(limit=10) == 2

    def test_id_hashing_deterministic(self):
        h1 = self.store._hash_id("test-user")
        h2 = self.store._hash_id("test-user")
        assert h1 == h2

    def test_id_hashing_different_per_input(self):
        h1 = self.store._hash_id("user-a")
        h2 = self.store._hash_id("user-b")
        assert h1 != h2

    def test_id_hashing_requires_salt(self):
        store_no_salt = ChannelStore(":memory:")
        store_no_salt._salt = ""
        try:
            store_no_salt._hash_id("test")
            assert False, "should have raised"
        except RuntimeError:
            pass

    def test_owner_allowlist_promotes_to_owner(self):
        user_hash = self.store._hash_id("owner-wx-id")
        os.environ["LIMA_CHANNEL_OWNER_HASHES"] = user_hash
        self.store.create_binding("bind_own", "wechat", "owner-wx-id", "Owner", "operator")
        binding = self.store.get_binding_by_channel_user("wechat", "owner-wx-id")
        assert binding.role == BindingRole.OWNER
        del os.environ["LIMA_CHANNEL_OWNER_HASHES"]

    def test_create_tables_migrates_legacy_bindings_without_role(self, tmp_path):
        db_path = str(tmp_path / "legacy_channel.db")
        legacy = ChannelStore(db_path)
        conn = legacy._get_conn()
        conn.execute(
            "CREATE TABLE channel_bindings ("
            " binding_id TEXT PRIMARY KEY,"
            " channel TEXT NOT NULL,"
            " channel_user_id_hash TEXT NOT NULL,"
            " display_name TEXT NOT NULL DEFAULT '',"
            " lima_user_id TEXT NOT NULL,"
            " status TEXT NOT NULL DEFAULT 'pending',"
            " created_at INTEGER NOT NULL,"
            " updated_at INTEGER NOT NULL"
            ")"
        )
        conn.commit()

        legacy._create_tables()
        columns = {
            row["name"]
            for row in legacy._get_conn().execute("PRAGMA table_info(channel_bindings)")
        }
        assert "role" in columns

        assert legacy.create_binding(
            "bind_legacy", "wechat", "legacy-user", "Legacy", "operator"
        )
        binding = legacy.get_binding_by_channel_user("wechat", "legacy-user")
        assert binding.role == BindingRole.GUEST


class TestEnsureGuestBinding:
    def setup_method(self):
        self.store = ChannelStore(":memory:")
        self.store._create_tables()

    def test_creates_active_guest_binding(self):
        binding, created = self.store.ensure_guest_binding("wechat", "wx-new-1")
        assert created is True
        assert binding is not None
        assert binding.status == BindingStatus.ACTIVE
        assert binding.role == BindingRole.GUEST
        assert binding.lima_user_id.startswith("wechat_guest_")

    def test_idempotent_when_already_active(self):
        self.store.ensure_guest_binding("wechat", "wx-same")
        binding2, created2 = self.store.ensure_guest_binding("wechat", "wx-same")
        assert created2 is False
        assert binding2.status == BindingStatus.ACTIVE

    def test_recreates_after_revoked(self):
        binding, _ = self.store.ensure_guest_binding("wechat", "wx-rev")
        self.store.set_binding_status(binding.binding_id, BindingStatus.REVOKED)
        binding2, created2 = self.store.ensure_guest_binding("wechat", "wx-rev")
        assert created2 is True
        assert binding2.status == BindingStatus.ACTIVE
