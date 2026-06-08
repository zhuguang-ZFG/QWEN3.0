"""Tests for retained five-line closeout slices: CF-G-3 and GI-G-5."""

from __future__ import annotations

from unittest.mock import MagicMock

import router_v3
from gitee_mirror import compare_mirror_heads, remote_head_sha


def test_chat_fast_strong_prefers_google_flash_lite():
    strong = router_v3.POOLS["chat_fast"]["strong"]
    assert strong[0] == "google_flash_lite"
    assert "google_flash_lite" not in router_v3.POOLS["chat_fast"]["medium"]


def test_vision_pool_includes_cf_and_google():
    strong = router_v3.POOLS["vision"]["strong"]
    assert "cf_vision" in strong
    assert "google_flash" in strong
    assert "github_gpt4o" in strong


def test_remote_head_sha_parses_output():
    def fake_run(cmd, **kwargs):
        return MagicMock(returncode=0, stdout="abc123 refs/heads/main\n", stderr="")

    sha, err = remote_head_sha("https://github.com/x/y.git", "main", runner=fake_run)
    assert sha == "abc123"
    assert err == ""


def test_compare_mirror_heads_in_sync():
    remote_v = (
        "origin\thttps://github.com/o/r.git (fetch)\n"
        "origin\thttps://github.com/o/r.git (push)\n"
        "gitee\thttps://gitee.com/o/r.git (push)\n"
    )

    def runner(cmd, **kwargs):
        if len(cmd) >= 4 and cmd[0] == "git" and cmd[-2:] == ["remote", "-v"]:
            return MagicMock(returncode=0, stdout=remote_v, stderr="")
        return MagicMock(returncode=0, stdout="deadbeef refs/heads/main\n", stderr="")

    result = compare_mirror_heads(".", "main", runner=runner)
    assert result["ok"] is True
    assert result["in_sync"] is True
