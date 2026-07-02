"""Regression tests for the unified VPS deploy helper."""

from __future__ import annotations

import sys

from scripts import deploy_unified
from scripts.deploy_unified_common import capacity_result, get_deploy_target, parse_capacity_output

from tests._deploy_mocks import _DeploySsh, _PrepareSsh, _RestartSsh, _Sftp


def test_deploy_files_uses_sftp_dirs_without_exec_channels(monkeypatch):
    import scripts.deploy_unified_deploy as deploy_mod

    monkeypatch.setenv("LIMA_DEPLOY_USE_TAR", "0")
    sftp = _Sftp()
    ssh = _DeploySsh(sftp)
    monkeypatch.setattr(deploy_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(deploy_mod, "configure_ssh_host_keys", lambda client: None)

    result = deploy_unified.deploy_files(["scripts/deploy_unified.py"], target=get_deploy_target("jdcloud"))

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
        lambda files, target, label: {"ok": True, "capacity": {}, "backup_path": "/tmp/unit.tgz"},
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: {"uploaded": 0, "failed": ["server.py: boom"], "skipped": []},
    )
    monkeypatch.setattr(
        deploy_unified,
        "restart_server",
        lambda target: (_ for _ in ()).throw(AssertionError("restart should not run after upload failure")),
    )

    assert deploy_unified.main() == 1


def test_main_rolls_back_when_health_check_fails(monkeypatch):
    rollback_calls: list[str] = []
    restart_calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server.py"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, target, label: {
            "ok": True,
            "capacity": {},
            "backup_path": "/opt/lima-router/backups/unit/runtime-before.tgz",
        },
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: {"uploaded": 1, "failed": [], "skipped": []},
    )

    def _restart(target: object) -> bool:
        restart_calls.append("restart")
        return len(restart_calls) > 1

    monkeypatch.setattr(deploy_unified, "restart_server", _restart)
    monkeypatch.setattr(
        deploy_unified,
        "restore_remote_backup",
        lambda backup_path, target: rollback_calls.append(backup_path) or True,
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
        lambda files, target, label: (_ for _ in ()).throw(AssertionError("preflight should not run in dry-run")),
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: (
            calls.append(f"dry={dry_run}") or {"uploaded": 0, "failed": [], "skipped": []}
        ),
    )

    assert deploy_unified.main() == 0
    assert calls == ["dry=True"]


def test_restart_server_uses_systemd_and_polls_health(monkeypatch):
    import scripts.deploy_unified_restart as restart_mod

    ssh = _RestartSsh()
    monkeypatch.setattr(restart_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(restart_mod, "configure_ssh_host_keys", lambda client: None)

    assert deploy_unified.restart_server(target=get_deploy_target("jdcloud")) is True

    assert deploy_unified.HEALTH_WAIT_SECONDS >= 60
    joined = "\n".join(ssh.commands)
    assert "systemctl restart lima-router" in ssh.commands
    assert "pkill" not in joined
    assert "nohup" not in joined
    assert any(command.startswith("curl ") for command in ssh.commands)
    assert ssh.closed is True


def test_parse_capacity_output():
    capacity = parse_capacity_output("disk_free_mb=2048\nmem_available_mb=512\n")

    assert capacity == {"disk_free_mb": 2048, "mem_available_mb": 512}


def test_capacity_result_rejects_low_disk_or_memory():
    low_disk = capacity_result(
        {"disk_free_mb": 128, "mem_available_mb": 512},
        min_free_mb=512,
        min_mem_mb=128,
    )
    low_mem = capacity_result(
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

    result = deploy_unified.prepare_remote_deploy(["server.py"], target=get_deploy_target("jdcloud"), label="unit test")

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

    ok = preflight_mod.restore_remote_backup(
        "/opt/lima-router/backups/unit/runtime-before.tgz", target=get_deploy_target("jdcloud")
    )

    assert ok is True
    assert any("tar -xzf" in command for command in ssh.commands)
    assert ssh.closed is True
