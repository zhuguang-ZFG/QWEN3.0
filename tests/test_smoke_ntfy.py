"""Tests for ntfy smoke helper."""

from __future__ import annotations

import scripts.smoke_ntfy as mod


def test_ntfy_url_from_topic(monkeypatch):
    monkeypatch.delenv("LIMA_NTFY_URL", raising=False)
    monkeypatch.setenv("LIMA_NTFY_TOPIC", "lima-test")
    monkeypatch.setenv("LIMA_NTFY_BASE", "https://ntfy.example.com")
    assert mod._ntfy_url() == "https://ntfy.example.com/lima-test"


def test_ntfy_url_explicit(monkeypatch):
    monkeypatch.setenv("LIMA_NTFY_URL", "https://ntfy.example.com/custom")
    assert mod._ntfy_url() == "https://ntfy.example.com/custom"
