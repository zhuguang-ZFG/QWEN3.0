"""Tests for Healthchecks.io dead-man ping helpers (INF-B)."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock

import healthcheck_ping as hc


def test_is_healthcheck_enabled_default_off(monkeypatch):
    monkeypatch.delenv("LIMA_HEALTHCHECK_ENABLED", raising=False)
    assert hc.is_healthcheck_enabled() is False


def test_is_healthcheck_enabled_on(monkeypatch):
    monkeypatch.setenv("LIMA_HEALTHCHECK_ENABLED", "1")
    assert hc.is_healthcheck_enabled() is True


def test_ping_healthcheck_success():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    client.get.return_value = response

    ok, detail = hc.ping_healthcheck("https://hc-ping.com/test-uuid", client=client)

    assert ok is True
    assert "200" in detail
    client.get.assert_called_once()


def test_ping_healthcheck_failure_status():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 500
    response.text = "error"
    client.get.return_value = response

    ok, detail = hc.ping_healthcheck("https://hc-ping.com/test-uuid", client=client)

    assert ok is False
    assert "500" in detail


def test_verify_health_endpoint_success():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    client.get.return_value = response

    ok, detail = hc.verify_health_endpoint("http://127.0.0.1:8080/health", client=client)

    assert ok is True
    client.get.assert_called_once()


def test_check_then_ping_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_HEALTHCHECK_ENABLED", "0")
    monkeypatch.setenv("HEALTHCHECK_LIMA_VPS_URL", "https://hc-ping.com/u")

    code = hc.check_then_ping(
        health_url="http://127.0.0.1:8080/health",
        ping_url="https://hc-ping.com/u",
    )

    assert code == hc.EXIT_SKIP


def test_check_then_ping_health_fail_no_ping(monkeypatch):
    monkeypatch.setenv("LIMA_HEALTHCHECK_ENABLED", "1")

    client = MagicMock()
    health_resp = MagicMock()
    health_resp.status_code = 503
    health_resp.text = "down"
    client.get.return_value = health_resp

    code = hc.check_then_ping(
        health_url="http://127.0.0.1:8080/health",
        ping_url="https://hc-ping.com/u",
        client=client,
    )

    assert code == hc.EXIT_HEALTH_FAIL
    assert client.get.call_count == 1


def test_check_then_ping_success(monkeypatch):
    monkeypatch.setenv("LIMA_HEALTHCHECK_ENABLED", "1")

    client = MagicMock()
    health_resp = MagicMock()
    health_resp.status_code = 200
    ping_resp = MagicMock()
    ping_resp.status_code = 200
    client.get.side_effect = [health_resp, ping_resp]

    code = hc.check_then_ping(
        health_url="http://127.0.0.1:8080/health",
        ping_url="https://hc-ping.com/u",
        client=client,
    )

    assert code == hc.EXIT_OK
    assert client.get.call_count == 2


def test_cli_dry_run():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/healthcheck_ping.py",
            "--ping-url",
            "https://hc-ping.com/example",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "example" in proc.stdout
    assert "hc-ping.com" in proc.stdout
