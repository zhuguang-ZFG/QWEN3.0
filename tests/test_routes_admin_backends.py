"""Tests for routes/admin_backends.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from routes import admin_backends


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/v1", True),
        ("http://example.com/v1", False),
        ("https://localhost:1234/v1", False),
        ("https://127.0.0.1/v1", False),
        ("https://192.168.1.1/v1", False),
        ("https://10.0.0.1/v1", False),
        ("file:///etc/passwd", False),
        ("not-a-url", False),
    ],
)
@patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))])
def test_is_safe_backend_url(_mock_getaddrinfo, url, expected):
    assert admin_backends._is_safe_backend_url(url) is expected


def test_resolve_vendor():
    assert admin_backends._resolve_vendor("https://longcat.ai/v1") == "LongCat"
    assert admin_backends._resolve_vendor("https://nvidia.com/v1") == "英伟达 NVIDIA"
    assert admin_backends._resolve_vendor("https://openrouter.ai/v1") == "OpenRouter"
    assert admin_backends._resolve_vendor("https://deepseek.com/v1") == "DeepSeek"
    assert admin_backends._resolve_vendor("https://example.com/v1") == "未知"


def test_resolve_tier():
    assert admin_backends._resolve_tier("https://example.com", "L3") == "L3"
    assert admin_backends._resolve_tier("https://longcat.ai/v1", "") == "L1 免费无限"
    assert admin_backends._resolve_tier("https://nvidia.com/v1", "") == "L2 免费额度"
    assert admin_backends._resolve_tier("https://openrouter.ai/v1", "") == "L3 免费限量"
    assert admin_backends._resolve_tier("https://example.com/v1", "") == "L4 付费"


def test_resolve_capabilities_with_cfg():
    assert admin_backends._resolve_capabilities("be", ["vision"]) == ["vision"]


def test_resolve_capabilities_inference():
    assert "工具调用" in admin_backends._resolve_capabilities("claude", [])
    assert "视觉" in admin_backends._resolve_capabilities("claude", [])
    assert "深度推理" in admin_backends._resolve_capabilities("deepseek_r1", [])
    assert admin_backends._resolve_capabilities("plain", []) == ["纯文本"]


def test_describe_backend():
    cfg = {
        "url": "https://example.com/v1",
        "model": "m1",
        "fmt": "openai",
        "key": "secret",
        "tier": "L2",
        "caps": ["vision"],
        "pools": ["p1"],
        "admission": "all",
    }
    result = admin_backends.describe_backend(
        "be1",
        cfg,
        enabled=True,
        status_info={"state": "closed", "total_calls": 5, "error_rate": "0.0%"},
    )
    assert result["name"] == "be1"
    assert result["enabled"] is True
    assert result["capabilities"] == ["vision"]
    assert result["key_configured"] is True
    assert result["pools"] == ["p1"]


def test_test_backend_sync_not_found():
    with patch.object(admin_backends, "BACKENDS", {}):
        result = admin_backends.test_backend_sync("missing")
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_test_backend_sync_unsafe_url():
    with patch.object(admin_backends, "BACKENDS", {"be1": {"url": "http://localhost:1234"}}):
        result = admin_backends.test_backend_sync("be1")
    assert result["ok"] is False
    assert "not a public HTTPS endpoint" in result["error"]


@patch("urllib.request.urlopen")
@patch.object(admin_backends, "_is_safe_backend_url", return_value=True)
def test_test_backend_sync_openai_ok(_mock_safe, mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"choices": [{"message": {"content": "hi"}}]}).encode()
    mock_urlopen.return_value = mock_resp
    with patch.object(
        admin_backends,
        "BACKENDS",
        {"be1": {"url": "https://example.com/v1", "key": "k", "fmt": "openai", "model": "m"}},
    ):
        result = admin_backends.test_backend_sync("be1")
    assert result["ok"] is True
    assert result["status"] == 200


@patch("urllib.request.urlopen")
@patch.object(admin_backends, "_is_safe_backend_url", return_value=True)
def test_test_backend_sync_anthropic_ok(_mock_safe, mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"content": [{"text": "hi"}]}).encode()
    mock_urlopen.return_value = mock_resp
    with patch.object(
        admin_backends,
        "BACKENDS",
        {"be1": {"url": "https://api.anthropic.com/v1", "key": "k", "fmt": "anthropic", "model": "m"}},
    ):
        result = admin_backends.test_backend_sync("be1")
    assert result["ok"] is True


@patch("urllib.request.urlopen", side_effect=Exception("timeout"))
@patch.object(admin_backends, "_is_safe_backend_url", return_value=True)
def test_test_backend_sync_request_error(_mock_safe, _mock_urlopen):
    with patch.object(
        admin_backends,
        "BACKENDS",
        {"be1": {"url": "https://example.com/v1", "key": "k", "fmt": "openai", "model": "m"}},
    ):
        result = admin_backends.test_backend_sync("be1")
    assert result["ok"] is False
    assert "timeout" in result["error"]
