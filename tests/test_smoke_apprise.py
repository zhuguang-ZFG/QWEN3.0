"""Tests for Apprise smoke script."""

from __future__ import annotations

import sys

import scripts.smoke_apprise as mod


def test_smoke_skip_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_APPRISE_SMOKE", "0")
    monkeypatch.setattr(sys, "argv", ["smoke_apprise.py"])
    assert mod.main() == 0


def test_smoke_skip_without_urls(monkeypatch):
    monkeypatch.setenv("LIMA_APPRISE_SMOKE", "1")
    monkeypatch.delenv("LIMA_APPRISE_URLS", raising=False)
    monkeypatch.setattr(sys, "argv", ["smoke_apprise.py"])
    assert mod.main() == 0
