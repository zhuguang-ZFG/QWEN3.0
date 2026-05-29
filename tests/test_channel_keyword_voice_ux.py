"""Keyword shortcuts + voice transcript display."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-kw-voice"
os.environ["LIMA_CHANNEL_SHOW_VOICE_TRANSCRIPT"] = "1"

from channel_gateway.keyword_router import normalize_guest_text
from channel_gateway.media_inbound import extract_voice_transcript
from channel_gateway.store import ChannelStore
from channel_gateway.service import ChannelService
from channel_gateway.models import InboundMessage


def test_keyword_menu():
    assert normalize_guest_text("菜单") == "/menu"


def test_keyword_site():
    assert normalize_guest_text("官网") == "/公司"


def test_keyword_weather_prefix():
    assert normalize_guest_text("天气 北京") == "/天气 北京"


def test_extract_voice_transcript_hint():
    t = extract_voice_transcript(
        "",
        [{"kind": "voice", "transcript_hint": "你好"}],
    )
    assert t == "你好"


def test_help_via_keyword():
    store = ChannelStore(":memory:")
    store._create_tables()
    svc = ChannelService(store=store, enabled=True)
    reply = svc.handle_message(
        InboundMessage(
            message_id="k1",
            sender_id="u-kw",
            conversation_id="c1",
            text="帮助",
        )
    )
    assert reply.ok
    assert "/menu" in reply.reply["text"] or "菜单" in reply.reply["text"]


def test_voice_transcript_prefix_in_chat(monkeypatch):
    store = ChannelStore(":memory:")
    store._create_tables()
    svc = ChannelService(store=store, enabled=True)
    svc._chat_handler = lambda _u, _t: "回复正文"
    reply = svc.handle_message(
        InboundMessage(
            message_id="v1",
            sender_id="u-v",
            conversation_id="c1",
            text="",
            attachments=[{"kind": "voice", "transcript_hint": "今天天气"}],
            voice_transcript="今天天气",
        )
    )
    assert reply.ok
    body = reply.reply["text"]
    assert "识别" in body
    assert "今天天气" in body
    assert "回复正文" in body
