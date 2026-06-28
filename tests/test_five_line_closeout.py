"""Tests for retained five-line closeout slice CF-G-3."""

from __future__ import annotations

import router_v3


def test_chat_fast_strong_prefers_google_flash_lite():
    strong = router_v3.POOLS["chat_fast"]["strong"]
    assert strong[0] == "google_flash_lite"
    assert "google_flash_lite" not in router_v3.POOLS["chat_fast"]["medium"]


def test_vision_pool_includes_cf_and_google():
    strong = router_v3.POOLS["vision"]["strong"]
    assert "cf_vision" in strong
    assert "google_flash" in strong
    assert "github_gpt4o" in strong
