"""Tests for deploy_common TG-GH-6 helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import paramiko

_scripts = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("deploy_common", _scripts / "deploy_common.py")
assert _spec and _spec.loader
deploy_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy_common)


def test_format_deploy_ok():
    text = deploy_common.format_deploy_ok("github_webhook", service="active", health='{"status":"ok"}')
    assert "Deploy OK: github_webhook" in text
    assert "service=active" in text


def test_format_smoke_ok():
    assert "Smoke OK: device_gateway" in deploy_common.format_smoke_ok("device_gateway", detail="4/4")


def test_configure_ssh_host_keys_rejects_unknown_hosts(monkeypatch):
    monkeypatch.delenv("LIMA_DEPLOY_KNOWN_HOSTS", raising=False)
    ssh = MagicMock()

    deploy_common.configure_ssh_host_keys(ssh)

    ssh.load_system_host_keys.assert_called_once_with()
    ssh.load_host_keys.assert_not_called()
    policy = ssh.set_missing_host_key_policy.call_args.args[0]
    assert isinstance(policy, paramiko.RejectPolicy)


def test_configure_ssh_host_keys_loads_extra_known_hosts(monkeypatch):
    monkeypatch.setenv("LIMA_DEPLOY_KNOWN_HOSTS", r"C:\known_hosts")
    ssh = MagicMock()

    deploy_common.configure_ssh_host_keys(ssh)

    ssh.load_host_keys.assert_called_once_with(r"C:\known_hosts")


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
