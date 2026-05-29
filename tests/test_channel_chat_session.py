"""Tests for WeChat channel multi-turn session (G3)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "session-test-salt"
os.environ["LIMA_CHANNEL_SESSION"] = "1"
os.environ["LIMA_CHANNEL_SESSION_TURNS"] = "3"

from channel_gateway.chat_session import ChannelChatSession, max_turns
from channel_gateway.store import ChannelStore


class TestChannelChatSession:
    def setup_method(self):
        self.store = ChannelStore(":memory:")
        self.store._create_tables()
        self.session = ChannelChatSession(self.store)

    def test_record_and_retrieve(self):
        self.session.record_turn("wx-1", "user", "hello")
        self.session.record_turn("wx-1", "assistant", "hi there")
        msgs = self.session.get_messages("wx-1")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "hi there"

    def test_trim_to_max_turns(self):
        for i in range(5):
            self.session.record_turn("wx-2", "user", f"u{i}")
            self.session.record_turn("wx-2", "assistant", f"a{i}")
        msgs = self.session.get_messages("wx-2")
        assert len(msgs) == max_turns() * 2

    def test_clear(self):
        self.session.record_turn("wx-3", "user", "x")
        self.session.clear("wx-3")
        assert self.session.get_messages("wx-3") == []
