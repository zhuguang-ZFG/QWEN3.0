"""Tests for WeChat channel public tools and quotas."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "channel-tools-test-salt"
os.environ["LIMA_CHANNEL_DB_PATH"] = ":memory:"
os.environ["LIMA_CHANNEL_TOOLS"] = "1"

from channel_gateway.commands import parse_command
from channel_gateway.channel_tools import run_channel_tool, CHANNEL_TOOL_INTENTS
from channel_gateway.store import ChannelStore
from channel_gateway import channel_tools as ct_mod


class TestChannelToolCommands:
    def test_chinese_aliases_map_to_intents(self):
        assert parse_command("/百科 Python").intent == "wiki"
        assert parse_command("/天气 北京").intent == "weather"
        assert parse_command("/搜 LiMa routing").intent == "search"
        assert parse_command("/读 https://example.com").intent == "read_url"
        assert parse_command("/新闻 AI").intent == "news"
        assert parse_command("/翻译 hello").intent == "translate"
        assert parse_command("/汇率 USD CNY").intent == "exchange"
        assert parse_command("/时间").intent == "time"
        assert parse_command("/热搜 微博").intent == "hot"
        assert parse_command("/ip 8.8.8.8").intent == "ip"
        assert parse_command("/算 1+1").intent == "calc"
        assert parse_command("/黄历").intent == "holiday"
        assert parse_command("/股票 AAPL").intent == "stock"
        assert parse_command("/地震").intent == "earthquake"
        assert parse_command("/menu").intent == "menu"

    def test_all_tool_intents_registered(self):
        for intent in (
            "wiki", "weather", "search", "read_url", "news",
            "translate", "exchange", "time", "hot", "ip", "menu",
            "calc", "holiday", "stock", "earthquake",
        ):
            assert intent in CHANNEL_TOOL_INTENTS


class TestChannelToolRunner:
    def setup_method(self):
        self.store = ChannelStore(":memory:")
        self.store._create_tables()

    def test_calc_local_no_network(self):
        text = run_channel_tool(
            self.store, "calc", "10/4",
            channel_user_id_raw="u-calc", role="guest",
        )
        assert "2.5" in text

    def test_wiki_mocked(self, monkeypatch):
        monkeypatch.setattr(
            ct_mod,
            "fetch_wiki",
            lambda q, **kw: {"ok": True, "text": f"wiki:{q}"},
        )
        text = run_channel_tool(
            self.store, "wiki", "Python",
            channel_user_id_raw="u-wiki", role="guest",
        )
        assert "wiki:Python" in text

    def test_tools_disabled_message(self, monkeypatch):
        monkeypatch.setenv("LIMA_CHANNEL_TOOLS", "0")
        text = run_channel_tool(
            self.store, "wiki", "x",
            channel_user_id_raw="u-off", role="guest",
        )
        assert "未开启" in text

    def test_quota_blocks_after_limit(self, monkeypatch):
        monkeypatch.setenv("LIMA_CHANNEL_TOOLS", "1")
        monkeypatch.setattr(
            ct_mod,
            "fetch_time",
            lambda tz="Asia/Shanghai": {"ok": True, "text": "now"},
        )
        user = "u-quota"
        for _ in range(30):
            run_channel_tool(
                self.store, "time", "",
                channel_user_id_raw=user, role="guest",
            )
        text = run_channel_tool(
            self.store, "time", "",
            channel_user_id_raw=user, role="guest",
        )
        assert "次数已用完" in text

    def test_menu_no_quota(self):
        text = run_channel_tool(
            self.store, "menu", "",
            channel_user_id_raw="u-menu", role="guest",
        )
        assert "/百科" in text


class TestToolUsageStore:
    def setup_method(self):
        self.store = ChannelStore(":memory:")
        self.store._create_tables()

    def test_consume_tool_quota(self):
        h = "abc123"
        ok1, c1 = self.store.consume_tool_quota(h, "wiki", 2, day="2026-05-25")
        ok2, c2 = self.store.consume_tool_quota(h, "wiki", 2, day="2026-05-25")
        ok3, c3 = self.store.consume_tool_quota(h, "wiki", 2, day="2026-05-25")
        assert ok1 and c1 == 1
        assert ok2 and c2 == 2
        assert not ok3 and c3 == 2
