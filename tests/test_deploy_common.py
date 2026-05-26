"""Tests for deploy_common TG-GH-6 helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deploy_common  # noqa: E402


def test_format_deploy_ok():
    text = deploy_common.format_deploy_ok("github_webhook", service="active", health='{"status":"ok"}')
    assert "Deploy OK: github_webhook" in text
    assert "service=active" in text


def test_format_smoke_ok():
    assert "Smoke OK: device_gateway" in deploy_common.format_smoke_ok("device_gateway", detail="4/4")


def test_notify_telegram_vps_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_DEPLOY_NOTIFY", "0")
    ssh = MagicMock()
    assert deploy_common.notify_telegram_vps(ssh, "hello") is False
    ssh.exec_command.assert_not_called()


def test_notify_telegram_vps_calls_remote(monkeypatch):
    monkeypatch.setenv("LIMA_DEPLOY_NOTIFY", "1")
    ssh = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = b"notify_ok\n"
    stderr = MagicMock()
    stderr.read.return_value = b""
    ssh.exec_command.return_value = (None, stdout, stderr)
    ok = deploy_common.notify_deploy_success(ssh, "test_slice", service="active")
    assert ok is True
    assert ssh.exec_command.called
