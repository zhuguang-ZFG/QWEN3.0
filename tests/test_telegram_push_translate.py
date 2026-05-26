"""Tests for telegram_push_translate (TG-GH-7)."""

from __future__ import annotations

import telegram_push_translate as tpt


def test_default_llm_backend_order():
    monkeypatch_backends = tpt.push_translate_backends()
    assert monkeypatch_backends[0] == "scnet_qwen30b"
    assert monkeypatch_backends[-1] == "google_flash_lite"


def test_translate_push_disabled(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PUSH_TRANSLATE", raising=False)
    assert tpt.translate_push_text("GitHub push") == "GitHub push"


def test_translate_push_skips_chinese(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    msg = "GitHub 24h: 1 push，Gitee 24h: 0"
    assert tpt.translate_push_text(msg) == msg


def test_translate_push_skips_digest(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    msg = "*LiMa Daily · 2026-05-26*\nBackends: 3 healthy"
    assert tpt.translate_push_text(msg) == msg


def test_translate_push_llm(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE_ENGINE", "llm")

    def fake_llm(text, *, target):
        assert "GitHub push" in text
        return "GitHub 推送"

    monkeypatch.setattr(tpt, "_translate_via_llm", fake_llm)
    out = tpt.translate_push_text("GitHub push `owner/repo`@main")
    assert "【译】GitHub 推送" in out


def test_translate_push_llm_fallback_mymemory(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE_ENGINE", "llm")
    monkeypatch.setattr(tpt, "_translate_via_llm", lambda *a, **k: None)

    def fake_mm(text, *, target):
        return "备用翻译"

    monkeypatch.setattr(tpt, "_translate_via_mymemory", fake_mm)
    out = tpt.translate_push_text("Deploy OK: test")
    assert "【译】备用翻译" in out


def test_translate_push_mymemory_engine(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE", "1")
    monkeypatch.setenv("TELEGRAM_PUSH_TRANSLATE_ENGINE", "mymemory")

    def fake_mm(text, *, target):
        return "MyMemory 译"

    monkeypatch.setattr(tpt, "_translate_via_mymemory", fake_mm)
    monkeypatch.setattr(
        tpt,
        "_translate_via_llm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("llm should not run")),
    )
    out = tpt.translate_push_text("Smoke OK: device")
    assert "【译】MyMemory 译" in out
