"""Tests for the JDCloud probe result push script."""

from __future__ import annotations

import importlib.util
import io
import json
import logging
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "deploy" / "jdcloud" / "push_probe_results.py"

_spec = importlib.util.spec_from_file_location("push_probe_results", SCRIPT_PATH)
assert _spec is not None
assert _spec.loader is not None
push_probe_results = importlib.util.module_from_spec(_spec)
sys.modules["push_probe_results"] = push_probe_results
_spec.loader.exec_module(push_probe_results)


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Return a temporary probe data directory."""
    return tmp_path


def test_build_payload_from_stability(data_dir: Path) -> None:
    _write_json(
        data_dir / "stability.json",
        {
            "groq": {
                "url": "https://api.groq.com/openai/v1",
                "checks": 10,
                "successes": 9,
                "last_success": "2026-06-28T12:00:00Z",
                "last_failure": "2026-06-28T11:00:00Z",
                "latencies": [100, 110, 120, 130],
            }
        },
    )
    _write_jsonl(
        data_dir / "discoveries.jsonl",
        [
            {
                "url": "https://api.groq.com/openai/v1",
                "source": "search",
                "name": "Groq",
                "is_free": True,
                "mentioned_models": ["llama3-8b"],
            }
        ],
    )

    payload = push_probe_results._build_payload(data_dir)

    assert payload["source"] == "jdcloud"
    assert len(payload["probes"]) == 1
    probe = payload["probes"][0]
    assert probe["provider"] == "groq"
    assert probe["status"] == "alive"
    assert probe["latency_ms"] == 115.0
    assert probe["price_tier"] == "free"
    assert probe["checked_at"] == "2026-06-28T12:00:00Z"
    assert probe["metadata"]["uptime_pct"] == 90.0
    assert probe["metadata"]["source"] == "search"
    assert probe["metadata"]["mentioned_models"] == ["llama3-8b"]


def test_build_payload_status_dead(data_dir: Path) -> None:
    _write_json(
        data_dir / "stability.json",
        {
            "openrouter": {
                "url": "https://openrouter.ai/api/v1",
                "checks": 5,
                "successes": 2,
                "last_success": "2026-06-28T10:00:00Z",
                "last_failure": "2026-06-28T12:00:00Z",
                "latencies": [],
            }
        },
    )

    payload = push_probe_results._build_payload(data_dir)

    probe = payload["probes"][0]
    assert probe["status"] == "dead"
    assert probe["latency_ms"] == -1.0
    assert probe["checked_at"] == "2026-06-28T12:00:00Z"


def test_build_payload_metadata_sanitization(data_dir: Path) -> None:
    _write_json(
        data_dir / "stability.json",
        {
            "example": {
                "url": "https://api.example.com",
                "checks": 1,
                "successes": 1,
                "last_success": "2026-06-28T12:00:00Z",
                "latencies": [50],
            }
        },
    )
    _write_jsonl(
        data_dir / "discoveries.jsonl",
        [
            {
                "url": "https://api.example.com",
                "source": "manual",
                "name": "Example",
                "mentioned_models": ["model-a"],
            }
        ],
    )

    payload = push_probe_results._build_payload(data_dir)
    metadata = payload["probes"][0]["metadata"]

    assert metadata["source"] == "manual"
    assert metadata["name"] == "Example"
    assert metadata["mentioned_models"] == ["model-a"]


def test_sanitize_metadata_strips_sensitive_keys() -> None:
    raw = {
        "region": "cn-north-1",
        "api_key": "super-secret",
        "nested": {"auth_token": "also-secret", "keep": "value"},
        "private_key": "should-be-removed-because-_key",
        "monkey": "keeper",
        "author": " preserved ",
    }
    sanitized = push_probe_results._sanitize_metadata(raw)

    assert "api_key" not in sanitized
    assert "private_key" not in sanitized
    assert "auth_token" not in sanitized.get("nested", {})
    assert sanitized["nested"]["keep"] == "value"
    assert sanitized["region"] == "cn-north-1"
    assert sanitized["monkey"] == "keeper"
    assert sanitized["author"] == " preserved "


def test_build_payload_falls_back_to_known_providers(data_dir: Path) -> None:
    _write_json(
        data_dir / "known_providers.json",
        {"urls": ["https://api.groq.com/openai/v1", "https://api.unknown.com/v1"]},
    )
    _write_jsonl(
        data_dir / "discoveries.jsonl",
        [
            {
                "url": "https://api.groq.com/openai/v1",
                "source": "search",
                "name": "Groq",
                "is_free": True,
            }
        ],
    )

    payload = push_probe_results._build_payload(data_dir)

    assert payload["source"] == "jdcloud"
    assert len(payload["probes"]) == 2
    by_provider = {p["provider"]: p for p in payload["probes"]}
    assert by_provider["api.groq.com/openai/v1"]["status"] == "unknown"
    assert by_provider["api.groq.com/openai/v1"]["price_tier"] == "free"
    assert by_provider["api.unknown.com/v1"]["price_tier"] == ""


def test_main_missing_token_logs_error_and_does_not_post(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    data_dir: Path,
) -> None:
    monkeypatch.delenv("LIMA_PROBE_INGRESS_TOKEN", raising=False)
    monkeypatch.setenv("PROBE_DATA_DIR", str(data_dir))

    posted: list[dict[str, Any]] = []
    monkeypatch.setattr(push_probe_results, "_post_payload", lambda *args, **kwargs: posted.append(args))

    with caplog.at_level(logging.ERROR):
        rc = push_probe_results.main()

    assert rc == 0
    assert not posted
    assert any("LIMA_PROBE_INGRESS_TOKEN" in record.message for record in caplog.records)


def test_main_skips_post_when_no_probe_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    data_dir: Path,
) -> None:
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "token")
    monkeypatch.setenv("PROBE_DATA_DIR", str(data_dir))

    posted: list[Any] = []
    monkeypatch.setattr(push_probe_results, "_post_payload", lambda *args, **kwargs: posted.append(args))

    with caplog.at_level(logging.INFO):
        rc = push_probe_results.main()

    assert rc == 0
    assert not posted
    assert any("nothing to push" in record.message for record in caplog.records)


def test_main_invalid_timeout_logs_error_and_does_not_post(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    data_dir: Path,
) -> None:
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "token")
    monkeypatch.setenv("PROBE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PROBE_INGRESS_TIMEOUT", "not-an-integer")

    posted: list[Any] = []
    monkeypatch.setattr(push_probe_results, "_post_payload", lambda *args, **kwargs: posted.append(args))

    with caplog.at_level(logging.ERROR):
        rc = push_probe_results.main()

    assert rc == 0
    assert not posted
    assert any("PROBE_INGRESS_TIMEOUT" in record.message for record in caplog.records)


def test_post_payload_logs_info_on_success(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeResponse:
        status = 200
        _body = b'{"recorded": 3}'

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args: object):
            return False

    monkeypatch.setattr(
        push_probe_results.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    with caplog.at_level(logging.INFO):
        push_probe_results._post_payload({"probes": []}, "https://example.com/ingress", "token", 30)

    assert any("status=200" in record.message and "recorded=3" in record.message for record in caplog.records)


def test_post_payload_logs_warning_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fp = io.BytesIO(b"unauthorized")
    error = urllib.error.HTTPError("https://example.com/ingress", 401, "Unauthorized", {}, fp)
    monkeypatch.setattr(
        push_probe_results.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error)
    )

    with caplog.at_level(logging.WARNING):
        push_probe_results._post_payload({"probes": []}, "https://example.com/ingress", "token", 30)

    assert any("HTTP 401" in record.message for record in caplog.records)


def test_post_payload_logs_warning_on_url_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = urllib.error.URLError("connection refused")
    monkeypatch.setattr(
        push_probe_results.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error)
    )

    with caplog.at_level(logging.WARNING):
        push_probe_results._post_payload({"probes": []}, "https://example.com/ingress", "token", 30)

    assert any("connection refused" in record.message for record in caplog.records)
