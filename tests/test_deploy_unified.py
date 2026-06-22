"""Regression tests for the unified VPS deploy helper."""

from __future__ import annotations

import sys

from scripts import deploy_unified


class _Channel:
    def __init__(self, status: int = 0) -> None:
        self._status = status

    def recv_exit_status(self) -> int:
        return self._status

    def shutdown_write(self) -> None:
        pass


class _Stdin:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.channel = _Channel()

    def write(self, data: str) -> None:
        self.writes.append(data)


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


class _PrepareSsh:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def exec_command(self, command: str) -> tuple[_Stdin, _Stream, _Stream]:
        self.commands.append(command)
        if "df -Pm" in command:
            return _Stdin(), _Stream("disk_free_mb=2048\nmem_available_mb=512\n"), _Stream()
        if "tar --ignore-failed-read" in command:
            return (
                _Stdin(),
                _Stream("/opt/lima-router/backups/unit-test-20260609_010203/runtime-before.tgz\n"),
                _Stream(),
            )
        return _Stdin(), _Stream(), _Stream()

    def close(self) -> None:
        self.closed = True


def test_deploy_files_uses_sftp_dirs_without_exec_channels(monkeypatch):
    import scripts.deploy_unified_deploy as deploy_mod

    sftp = _Sftp()
    ssh = _DeploySsh(sftp)
    monkeypatch.setattr(deploy_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(deploy_mod, "configure_ssh_host_keys", lambda client: None)

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
        "prepare_remote_deploy",
        lambda files, label: {"ok": True, "capacity": {}, "backup_path": "/tmp/unit.tgz"},
    )
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


def test_main_rolls_back_when_health_check_fails(monkeypatch):
    rollback_calls: list[str] = []
    restart_calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server.py"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, label: {
            "ok": True,
            "capacity": {},
            "backup_path": "/opt/lima-router/backups/unit/runtime-before.tgz",
        },
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, dry_run=False: {"uploaded": 1, "failed": [], "skipped": []},
    )

    def _restart() -> bool:
        restart_calls.append("restart")
        return len(restart_calls) > 1

    monkeypatch.setattr(deploy_unified, "restart_server", _restart)
    monkeypatch.setattr(
        deploy_unified,
        "restore_remote_backup",
        lambda backup_path: rollback_calls.append(backup_path) or True,
    )

    assert deploy_unified.main() == 1
    assert rollback_calls == ["/opt/lima-router/backups/unit/runtime-before.tgz"]
    assert restart_calls == ["restart", "restart"]


def test_main_dry_run_does_not_open_remote_preflight(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server.py", "--dry-run"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, label: (_ for _ in ()).throw(AssertionError("preflight should not run in dry-run")),
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, dry_run=False: calls.append(f"dry={dry_run}") or {"uploaded": 0, "failed": [], "skipped": []},
    )

    assert deploy_unified.main() == 0
    assert calls == ["dry=True"]


def test_restart_server_uses_systemd_and_polls_health(monkeypatch):
    import scripts.deploy_unified_restart as restart_mod

    ssh = _RestartSsh()
    monkeypatch.setattr(restart_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(restart_mod, "configure_ssh_host_keys", lambda client: None)

    assert deploy_unified.restart_server() is True

    assert deploy_unified.HEALTH_WAIT_SECONDS >= 60
    joined = "\n".join(ssh.commands)
    assert "systemctl restart lima-router" in ssh.commands
    assert "pkill" not in joined
    assert "nohup" not in joined
    assert any(command.startswith("curl ") for command in ssh.commands)
    assert ssh.closed is True


def test_parse_capacity_output():
    capacity = deploy_unified.parse_capacity_output("disk_free_mb=2048\nmem_available_mb=512\n")

    assert capacity == {"disk_free_mb": 2048, "mem_available_mb": 512}


def test_capacity_result_rejects_low_disk_or_memory():
    low_disk = deploy_unified.capacity_result(
        {"disk_free_mb": 128, "mem_available_mb": 512},
        min_free_mb=512,
        min_mem_mb=128,
    )
    low_mem = deploy_unified.capacity_result(
        {"disk_free_mb": 2048, "mem_available_mb": 64},
        min_free_mb=512,
        min_mem_mb=128,
    )

    assert low_disk["ok"] is False
    assert "disk" in low_disk["reason"]
    assert low_mem["ok"] is False
    assert "memory" in low_mem["reason"]


def test_prepare_remote_deploy_checks_capacity_and_creates_backup(monkeypatch):
    import scripts.deploy_unified_common as common_mod
    import scripts.deploy_unified_preflight as preflight_mod

    ssh = _PrepareSsh()
    monkeypatch.setattr(common_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(common_mod, "configure_ssh_host_keys", lambda client: None)
    monkeypatch.setattr(preflight_mod.time, "strftime", lambda fmt: "20260609_010203")

    result = deploy_unified.prepare_remote_deploy(["server.py"], label="unit test")

    assert result["ok"] is True
    assert result["capacity"] == {"disk_free_mb": 2048, "mem_available_mb": 512}
    assert result["backup_path"] == "/opt/lima-router/backups/unit-test-20260609_010203/runtime-before.tgz"
    assert any("df -Pm" in command for command in ssh.commands)
    assert any("tar --ignore-failed-read" in command for command in ssh.commands)
    assert ssh.closed is True


def test_restore_remote_backup_extracts_tar(monkeypatch):
    import scripts.deploy_unified_common as common_mod
    import scripts.deploy_unified_preflight as preflight_mod

    ssh = _PrepareSsh()
    monkeypatch.setattr(common_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(common_mod, "configure_ssh_host_keys", lambda client: None)

    ok = preflight_mod.restore_remote_backup("/opt/lima-router/backups/unit/runtime-before.tgz")

    assert ok is True
    assert any("tar -xzf" in command for command in ssh.commands)
    assert ssh.closed is True
