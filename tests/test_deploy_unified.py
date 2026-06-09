"""Regression tests for the unified VPS deploy helper."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from scripts import deploy_unified


class _Channel:
    def __init__(self, status: int = 0) -> None:
        self._status = status

    def recv_exit_status(self) -> int:
        return self._status


class _Stream:
    def __init__(self, text: str = "", status: int = 0) -> None:
        self._text = text
        self.channel = _Channel(status)

    def read(self) -> bytes:
        return self._text.encode()


class _Sftp:
    def __init__(self) -> None:
        self.dirs = {"/"}
        self.mkdir_calls: list[str] = []
        self.put_calls: list[tuple[str, str]] = []
        self.closed = False

    def stat(self, path: str) -> object:
        if path not in self.dirs:
            raise FileNotFoundError(path)
        return object()

    def mkdir(self, path: str) -> None:
        self.mkdir_calls.append(path)
        self.dirs.add(path)

    def put(self, local: str, remote: str) -> None:
        self.put_calls.append((local, remote))

    def close(self) -> None:
        self.closed = True


class _DeploySsh:
    def __init__(self, sftp: _Sftp) -> None:
        self.sftp = sftp
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def open_sftp(self) -> _Sftp:
        return self.sftp

    def exec_command(self, command: str) -> tuple[None, _Stream, _Stream]:
        raise AssertionError(f"deploy_files should not open exec channels: {command}")

    def close(self) -> None:
        self.closed = True


class _RestartSsh:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def exec_command(self, command: str) -> tuple[None, _Stream, _Stream]:
        self.commands.append(command)
        if command.startswith("curl "):
            return None, _Stream('{"status":"ok"}'), _Stream()
        return None, _Stream(), _Stream()

    def close(self) -> None:
        self.closed = True


def test_deploy_files_uses_sftp_dirs_without_exec_channels(monkeypatch):
    sftp = _Sftp()
    ssh = _DeploySsh(sftp)
    monkeypatch.setattr(deploy_unified.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(deploy_unified, "configure_ssh_host_keys", lambda client: None)

    result = deploy_unified.deploy_files(["scripts/deploy_unified.py"])

    assert result == {"uploaded": 1, "failed": [], "skipped": []}
    assert sftp.put_calls[0][1] == "/opt/lima-router/scripts/deploy_unified.py"
    assert "/opt/lima-router/scripts" in sftp.dirs
    assert sftp.closed is True
    assert ssh.closed is True


def test_main_returns_failure_without_restart_when_upload_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server.py"])
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, dry_run=False: {"uploaded": 0, "failed": ["server.py: boom"], "skipped": []},
    )
    monkeypatch.setattr(
        deploy_unified,
        "restart_server",
        lambda: (_ for _ in ()).throw(AssertionError("restart should not run after upload failure")),
    )

    assert deploy_unified.main() == 1


def test_restart_server_uses_systemd_and_polls_health(monkeypatch):
    ssh = _RestartSsh()
    monkeypatch.setattr(deploy_unified.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(deploy_unified, "configure_ssh_host_keys", lambda client: None)

    assert deploy_unified.restart_server() is True

    assert deploy_unified.HEALTH_WAIT_SECONDS >= 90
    joined = "\n".join(ssh.commands)
    assert "systemctl restart lima-router" in ssh.commands
    assert "pkill" not in joined
    assert "nohup" not in joined
    assert any(command.startswith("curl ") for command in ssh.commands)
    assert ssh.closed is True
