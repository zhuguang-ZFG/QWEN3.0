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
    assert isinstance(report.get("hints"), list)


def test_probe_chat_sse_stream():
    sse = (
        'data: {"choices":[{"delta":{"content":"pong"}}]}\n\n'
        'data: [DONE]\n\n'
    )
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = sse.encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    with patch("oldllm_diag.urllib.request.urlopen") as urlopen:
        urlopen.return_value = resp
        result = oldllm_diag.probe_chat("http://127.0.0.1:4502", timeout=5)
    assert result["ok"] is True
    assert result["content_sample"] == "pong"


def test_parse_sse_chat_message_shape():
    raw = 'data: {"choices":[{"message":{"content":"hello"}}]}\n\n'
    assert oldllm_diag._parse_sse_chat(raw) == "hello"


def test_run_diag_skips_unreachable_local_proxy():
    def fake_models(base: str):
        if "4502" in base:
            return {
                "target": base,
                "kind": "models",
                "ok": False,
                "status": None,
                "elapsed_sec": 0.001,
                "model_count": 0,
                "models_sample": [],
                "error": "URLError",
            }
        return {
            "target": base,
            "kind": "models",
            "ok": True,
            "status": 200,
            "elapsed_sec": 0.2,
            "model_count": 2,
            "models_sample": ["a"],
            "error": None,
        }

    with patch("oldllm_diag.probe_models", side_effect=fake_models), patch("oldllm_diag.probe_chat") as chat:
        chat.return_value = {
            "target": "https://up.test",
            "kind": "chat",
            "ok": False,
            "status": 502,
            "elapsed_sec": 0.5,
            "timed_out": False,
            "content_sample": "",
            "error": "502",
        }
        report = oldllm_diag.run_diag(
            upstream="https://up.test",
            local_proxy="http://127.0.0.1:4502",
        )
    local = [r for r in report["results"] if r.get("label") == "local_proxy"]
    assert all(r.get("skipped") for r in local)
    chat.assert_called_once()


def test_failure_hints_502():
    report = {
        "any_models_ok": True,
        "any_chat_ok": False,
        "results": [
            {
                "label": "local_proxy",
                "kind": "chat",
                "ok": False,
                "status": 502,
                "timed_out": False,
            }
        ],
    }
    hints = oldllm_diag.failure_hints(report)
    assert any("502" in h for h in hints)
