"""Wave 1: NL tools, voice reply pack, invite QR flag."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-wave1"
os.environ["LIMA_CHANNEL_VOICE_REPLY"] = "1"
os.environ["LIMA_CHANNEL_INVITE_QR"] = "1"

from channel_gateway.keyword_router import normalize_guest_text
from channel_gateway.nl_tool_router import match_nl_tool
from channel_gateway.outbound_pack import pack_text_reply
from channel_gateway.invite import invite_text
from channel_gateway.voice_reply import (
    parse_voice_reply_command,
    should_attach_voice_reply,
    voice_reply_snippet,
    voice_reply_tts_text,
)
from channel_gateway.store import ChannelStore
from channel_gateway.service import ChannelService
from channel_gateway.models import InboundMessage


def test_nl_weather_city_suffix():
    assert match_nl_tool("北京的天气") == "/天气 北京"


def test_nl_calc():
    assert match_nl_tool("算一下 1+2*3") == "/算 1+2*3"


def test_nl_search():
    assert normalize_guest_text("搜一下 Python asyncio") == "/搜 Python asyncio"


def test_nl_time():
    assert normalize_guest_text("现在几点了") == "/时间"


def test_voice_reply_toggle_parse():
    assert parse_voice_reply_command("/语音回复 off") == "off"
    assert parse_voice_reply_command("语音回复 开") == "on"


def test_pack_voice_on_inbound_voice():
    msg = InboundMessage(
        message_id="w1",
        sender_id="u1",
        conversation_id="c1",
        text="",
        attachments=[{"kind": "voice", "transcript_hint": "你好"}],
        voice_transcript="你好",
    )
    packed = pack_text_reply("这是回复", msg)
    assert packed.get("voice_reply_text") == "这是回复"


def test_pack_voice_tts_short_on_inbound_voice():
    msg = InboundMessage(
        "w1c",
        "u1",
        "c1",
        voice_transcript="你好",
    )
    long_answer = "你好呀！我是 LiMa。" + "可以随时问我编程问题。" * 5
    packed = pack_text_reply(long_answer, msg)
    tts = packed.get("voice_reply_text") or ""
    assert tts
    assert len(tts) <= 96
    assert "编程问题" not in tts or len(tts) <= 40


def test_pack_invite_qr_flag():
    msg = InboundMessage("w2", "u1", "c1", text="/邀请")
    svc = ChannelService(store=ChannelStore(":memory:"), enabled=True)
    store = svc._store
    store._create_tables()
    store.create_binding("b1", "wechat", "u1", "u1", "guest")
    reply = svc.handle_message(msg)
    assert reply.ok
    assert reply.reply.get("send_invite_qr") is not True


def test_voice_snippet_strips_footer_and_emoji():
    long = "你好呀！😊 我是 LiMa。" + "x" * 600 + "\n—— 公司尾注"
    snip = voice_reply_snippet(long)
    assert snip
    assert len(snip) <= 320
    assert "——" not in snip
    assert "😊" not in snip


def test_pack_voice_on_long_inbound_voice():
    msg = InboundMessage(
        message_id="w1b",
        sender_id="u1",
        conversation_id="c1",
        voice_transcript="你好",
    )
    long_answer = "你好呀！😊 " + ("助手回复 " * 80) + "\n—— 深圳市动力巢"
    packed = pack_text_reply(long_answer, msg)
    assert packed.get("voice_reply_text")
    assert len(packed["voice_reply_text"]) <= 320


def test_invite_text_web_only_retired_wechat(monkeypatch):
    monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "demo@im.bot")
    body = invite_text(share_url="https://liteapp.weixin.qq.com/q/x")
    assert "https://liteapp" not in body
    assert "chat.donglicao.com" in body
    assert "WECHAT_RETIRED" in body or "已停用" in body
    assert "小号" not in body
    assert "WCF" not in body


def test_should_not_voice_when_disabled_pref():
    msg = InboundMessage(
        "w3",
        "u1",
        "c1",
        attachments=[{"kind": "voice"}],
        voice_transcript="x",
    )
    assert should_attach_voice_reply(msg, "短回复", user_pref_on=False) is False
