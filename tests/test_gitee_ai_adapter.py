"""Tests for Gitee AI adapter (GI-G-3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from provider_automation.adapters import gitee_ai


def test_model_slug_and_backend_key():
    assert gitee_ai.backend_key_from_model("Qwen3.5-9B") == "gitee_qwen3_5_9b"
    assert gitee_ai.is_chat_candidate("Qwen3.5-9B") is True
    assert gitee_ai.is_chat_candidate("ViduQ3-Pro") is False


def test_classify_resource_not_bound():
    payload = {"error": {"code": "400", "message": "资源未购买或未授权,请购买或授权资源后再使用"}}
    assert gitee_ai.classify_error_payload(payload) == "resource_not_bound"


def test_build_backend_config_uses_env(monkeypatch):
    monkeypatch.setenv("GITEE_AI_TOKEN", "test-token")
    monkeypatch.setenv("GITEE_AI_BASE_URL", "https://ai.gitee.com/v1")
    cfg = gitee_ai.build_backend_config("Qwen3.5-9B")
    assert cfg["model"] == "Qwen3.5-9B"
    assert cfg["key"] == "test-token"
    assert cfg["url"].endswith("/chat/completions")
    assert cfg["admission"] == "chat_floor_only"


def test_probe_model_ok(monkeypatch):
    monkeypatch.setattr(
        gitee_ai,
        "call_gitee_chat",
        lambda model_id, messages, max_tokens=8, client=None: ("OK", 120.0),
    )
    result = gitee_ai.probe_model("Qwen3.5-9B")
    assert result["ok"] is True
    assert result["backend_key"] == "gitee_qwen3_5_9b"


def test_probe_model_resource_error(monkeypatch):
    def _fail(*args, **kwargs):
        raise RuntimeError("resource_not_bound: no package")

    monkeypatch.setattr(gitee_ai, "call_gitee_chat", _fail)
    result = gitee_ai.probe_model("Qwen3.5-9B")
    assert result["ok"] is False
    assert result["reason"] == "resource_not_bound"


def test_fetch_models_parses_list(monkeypatch):
    monkeypatch.setenv("GITEE_AI_TOKEN", "tok")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"id": "Qwen3.5-9B"}, {"id": "ViduQ3-Pro"}],
    }
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=mock_client):
        inv = gitee_ai.fetch_models()
    assert inv["model_count"] == 2
    assert inv["models"][0]["model_id"] == "Qwen3.5-9B"
