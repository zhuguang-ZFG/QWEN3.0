"""Tests for telegram_push_translate (TG-GH-7)."""

from __future__ import annotations

import telegram_push_translate as tpt


def test_translate_push_disabled(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PUSH_TRANSLATE", raising=False)
    assert tpt.translate_push_text("GitHub push") == "GitHub push"


def test_translate_push_skips_chinese(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    msg = "GitHub 24h: 1 push，Gitee 24h: 0"
    assert tpt.translate_push_text(msg) == msg


def test_translate_push_calls_mymemory(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")

    def fake_translate(text, *, target="zh-CN", max_len=500):
        assert "GitHub push" in text
        return "GitHub 推送"

    monkeypatch.setattr(
        "channel_gateway.public_apis.translate_text_only",
        fake_translate,
    )
    out = tpt.translate_push_text("GitHub push `owner/repo`@main")
    assert "【译】GitHub 推送" in out
    assert "GitHub push" in out
