"""Branding + media inbound for WeChat channel."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-brand-media"
os.environ["LIMA_CHANNEL_BRAND_FOOTER"] = "1"

from channel_gateway.branding import company_pitch, maybe_brand_footer
from channel_gateway.media_inbound import resolve_media_to_text
from channel_gateway.store import ChannelStore
from channel_gateway.service import ChannelService
from channel_gateway.models import InboundMessage


def _store():
    s = ChannelStore(":memory:")
    s._create_tables()
    return s


def _inbound(**kw):
    defaults = dict(
        message_id="m1",
        sender_id="u-brand",
        conversation_id="c1",
        text="",
    )
    defaults.update(kw)
    return InboundMessage(**defaults)


def test_company_pitch_has_donglicao():
    assert "动力巢" in company_pitch()
    assert "donglilicao.com" in company_pitch()


def test_brand_footer_appended():
    out = maybe_brand_footer("hello")
    assert "动力巢" in out


def test_voice_hint_becomes_text():
    text = resolve_media_to_text(
        "",
        [{"kind": "voice", "transcript_hint": "今天天气怎么样"}],
    )
    assert "语音转写" in text
    assert "天气" in text


def test_voice_stt_calls_mimo_first(monkeypatch):
    import channel_gateway.media_inbound as mi

    monkeypatch.setattr(
        mi,
        "_stt_audio",
        lambda *a, **k: "mimo-ok",
    )
    text = resolve_media_to_text(
        "",
        [{"kind": "voice", "data_b64": "YWJj", "mime": "audio/silk"}],
    )
    assert "mimo-ok" in text or "语音" in text


def test_company_command():
    svc = ChannelService(store=_store(), enabled=True)
    reply = svc.handle_message(_inbound(text="/公司"))
    assert reply.ok
    assert "动力巢" in reply.reply["text"]


def test_voice_help_command():
    svc = ChannelService(store=_store(), enabled=True)
    reply = svc.handle_message(_inbound(text="/语音"))
    assert reply.ok
    assert "语音" in reply.reply["text"]
