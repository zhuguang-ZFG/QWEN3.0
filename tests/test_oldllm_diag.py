"""Unit tests for TheOldLLM diagnosis helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import oldllm_diag


def _mock_response(status: int, payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_probe_models_ok():
    payload = {"data": [{"id": "gpt-4.1-nano"}, {"id": "gpt-5"}]}
    with patch("oldllm_diag.urllib.request.urlopen") as urlopen:
        urlopen.return_value = _mock_response(200, payload)
        result = oldllm_diag.probe_models("https://example.test")
    assert result["ok"] is True
    assert result["model_count"] == 2
    assert result["status"] == 200


def test_probe_models_empty():
    with patch("oldllm_diag.urllib.request.urlopen") as urlopen:
        urlopen.return_value = _mock_response(200, {"data": []})
        result = oldllm_diag.probe_models("https://example.test")
    assert result["ok"] is False
    assert result["model_count"] == 0


def test_probe_chat_ok():
    payload = {
        "choices": [{"message": {"content": "pong"}}],
    }
    with patch("oldllm_diag.urllib.request.urlopen") as urlopen:
        urlopen.return_value = _mock_response(200, payload)
        result = oldllm_diag.probe_chat("http://127.0.0.1:4502", timeout=5)
    assert result["ok"] is True
    assert result["content_sample"] == "pong"


def test_probe_chat_timeout():
    with patch(
        "oldllm_diag.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    ):
        result = oldllm_diag.probe_chat("http://127.0.0.1:4502", timeout=1)
    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["status"] is None


def test_run_diag_skip_chat():
    with patch("oldllm_diag.probe_models") as models:
        models.return_value = {
            "target": "x",
            "kind": "models",
            "ok": True,
            "status": 200,
            "elapsed_sec": 0.1,
            "model_count": 1,
            "models_sample": ["m"],
            "error": None,
        }
        report = oldllm_diag.run_diag(
            upstream="https://up.test",
            local_proxy="http://127.0.0.1:4502",
            skip_chat=True,
        )
    assert report["any_models_ok"] is True
    assert report["any_chat_ok"] is False
    assert len(report["results"]) == 2
