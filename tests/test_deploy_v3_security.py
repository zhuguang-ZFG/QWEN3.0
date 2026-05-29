"""Security tests for deploy SSH host key policy (canonical: deploy_common)."""

from __future__ import annotations

import sys
from pathlib import Path

import paramiko

# Legacy deploy_v3 moved to scripts/archive — test the canonical version
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "archive" / "deploy_legacy"))
import deploy_v3


class FakeSSHClient:
    def __init__(self) -> None:
        self.loaded_system = False
        self.loaded_paths: list[str] = []
        self.policy = None

    def load_system_host_keys(self) -> None:
        self.loaded_system = True

    def load_host_keys(self, path: str) -> None:
        self.loaded_paths.append(path)

    def set_missing_host_key_policy(self, policy) -> None:
        self.policy = policy


def test_configure_host_key_policy_rejects_unknown_hosts(monkeypatch):
    monkeypatch.delenv("LIMA_DEPLOY_KNOWN_HOSTS", raising=False)
    ssh = FakeSSHClient()

    deploy_v3._configure_host_key_policy(ssh)

    assert ssh.loaded_system is True
    assert ssh.loaded_paths == []
    assert isinstance(ssh.policy, paramiko.RejectPolicy)


def test_configure_host_key_policy_loads_extra_known_hosts(monkeypatch):
    monkeypatch.setenv("LIMA_DEPLOY_KNOWN_HOSTS", r"C:\known_hosts")
    ssh = FakeSSHClient()

    deploy_v3._configure_host_key_policy(ssh)

    assert ssh.loaded_paths == [r"C:\known_hosts"]
    assert isinstance(ssh.policy, paramiko.RejectPolicy)
