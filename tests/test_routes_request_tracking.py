"""Tests for routes/request_tracking.py."""

from __future__ import annotations

import json
import threading
import time
from unittest.mock import patch

import pytest
from fastapi import Request

from routes import request_tracking as rt


def _request(client_host: str, headers: dict | None = None) -> Request:
    return Request({"type": "http", "client": (client_host, 0), "headers": [[k.lower().encode(), v.encode()] for k, v in (headers or {}).items()]})


def test_client_ip_returns_direct_for_untrusted():
    assert rt.client_ip(_request("8.8.8.8")) == "8.8.8.8"


def test_client_ip_uses_xff_for_trusted():
    req = _request("127.0.0.1", {"X-Forwarded-For": "203.0.113.1, 10.0.0.2"})
    assert rt.client_ip(req) == "203.0.113.1"


def test_client_ip_uses_cf_connecting_ip():
    req = _request("127.0.0.1", {"CF-Connecting-IP": "198.51.100.5"})
    assert rt.client_ip(req) == "198.51.100.5"


def test_client_ip_uses_x_real_ip():
    req = _request("127.0.0.1", {"X-Real-IP": "192.0.2.10"})
    assert rt.client_ip(req) == "192.0.2.10"


def test_detect_ide_empty():
    assert rt.detect_ide([]) == ""


def test_detect_ide_claude():
    assert rt.detect_ide([{"role": "system", "content": "You are Claude Code"}]) == "Claude Code"


def test_detect_ide_cursor():
    assert rt.detect_ide([{"role": "system", "content": "You are Cursor"}]) == "Cursor"


def test_elapsed_ms():
    start = time.time() - 0.123
    ms = rt.elapsed_ms(start)
    assert 120 <= ms <= 130


def test_record_fallback_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "fallback_log.jsonl"
    monkeypatch.setattr(rt, "FALLBACK_LOG", str(log_path))
    rt.record_fallback("query", "a", "b", "chat", "vscode")
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["original_backend"] == "a"
    assert entry["fallback_backend"] == "b"


def test_record_request_updates_stats():
    stats = {
        "total_requests": 0,
        "backend_calls": {},
        "intent_distribution": {},
        "recent_logs": [],
    }
    lock = threading.Lock()
    rt.inject_state(stats, lock)
    rt.record_request("hi", "backend", "chat", 42, success=True, client_ip="127.0.0.1", ide_source="vscode")
    assert stats["total_requests"] == 1
    assert stats["backend_calls"]["backend"]["count"] == 1
    assert stats["backend_calls"]["backend"]["success"] == 1
    assert stats["intent_distribution"]["chat"] == 1


def test_get_ip_location_localhost():
    assert rt.get_ip_location("127.0.0.1") == "本地"


def test_get_ip_location_invalid():
    assert rt.get_ip_location("not-an-ip") == "未知"


@patch("urllib.request.urlopen")
def test_get_ip_location_lookup(mock_urlopen):
    mock_urlopen.return_value.read.return_value = json.dumps({"country": "China", "city": "Beijing"}).encode()
    assert rt.get_ip_location("1.2.3.4") == "China Beijing"
