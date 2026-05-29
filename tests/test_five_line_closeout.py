"""Tests for five-line closeout slices: CF-G-3, TG-GH-4, GI-G-5."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import router_v3
from gitee_mirror import compare_mirror_heads, remote_head_sha
from telegram_operator_tools import format_github_read, parse_github_args


def test_chat_fast_strong_prefers_google_flash_lite():
    strong = router_v3.POOLS["chat_fast"]["strong"]
    assert strong[0] == "google_flash_lite"
    assert "google_flash_lite" not in router_v3.POOLS["chat_fast"]["medium"]


def test_vision_pool_includes_cf_and_google():
    medium = router_v3.POOLS["vision"]["medium"]
    assert medium[0] == "cf_vision"
    assert "google_flash" in medium
    assert "github_gpt4o" in medium


def test_parse_github_args():
    assert parse_github_args("psf/requests README.md main") == ("psf/requests", "README.md", "main")
    assert parse_github_args("bad") is None


def test_format_github_read_ok():
    text = format_github_read({"ok": True, "title": "README", "text": "hello"})
    assert "README" in text
    assert "hello" in text
    assert text.startswith("README\n---\n")


@pytest.mark.asyncio
async def test_fetch_device_gateway_status():
    from telegram_operator_tools import fetch_device_gateway_status

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "ok",
        "protocol": "lima-device-v1",
        "task_store": {"backend": "redis"},
        "session_bus": {"listener_alive": True},
    }
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    text = await fetch_device_gateway_status(client=client, root="http://test")
    assert "Device Gateway" in text
    assert "redis" in text


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
