"""Regression tests for the unified VPS deploy helper."""

from __future__ import annotations

import sys

from scripts import deploy_unified
from scripts.deploy_unified_common import capacity_result, get_deploy_target, parse_capacity_output

from tests._deploy_mocks import _DeploySsh, _PrepareSsh, _RestartSsh, _Sftp, _TarDeploySsh


def test_deploy_files_uses_sftp_dirs_without_exec_channels(monkeypatch):
    import scripts.deploy_unified_ssh as ssh_mod

    monkeypatch.setenv("LIMA_DEPLOY_USE_TAR", "0")
    sftp = _Sftp()
    ssh = _DeploySsh(sftp)
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)

    result = deploy_unified.deploy_files(["scripts/deploy_unified.py"], target=get_deploy_target("jdcloud"))

    assert result == {"uploaded": 1, "failed": [], "skipped": []}
    assert sftp.put_calls[0][1] == "/opt/dlc-drawing/scripts/deploy_unified.py"
    assert "/opt/dlc-drawing/scripts" in sftp.dirs
    assert sftp.closed is True
    assert ssh.closed is True


def test_deploy_files_uses_tar_archive_via_paramiko(monkeypatch):
    import scripts.deploy_unified_ssh as ssh_mod

    monkeypatch.delenv("LIMA_DEPLOY_USE_TAR", raising=False)
    sftp = _Sftp()
    ssh = _TarDeploySsh(sftp)
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)

    result = deploy_unified.deploy_files(["scripts/deploy_unified.py"], target=get_deploy_target("jdcloud"))

    assert result == {"uploaded": 1, "failed": [], "skipped": []}
    assert len(sftp.put_calls) == 1
    assert sftp.put_calls[0][1].startswith("/tmp/lima-deploy-")
    assert sftp.put_calls[0][1].endswith(".tar.gz")
    assert any("tar -xzf" in cmd and "/opt/dlc-drawing" in cmd for cmd in ssh.commands)
    assert sftp.closed is True
    assert ssh.closed is True


def test_main_returns_failure_without_restart_when_upload_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server_dlc.py"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, target, label: {"ok": True, "capacity": {}, "backup_path": "/tmp/unit.tgz"},
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: {"uploaded": 0, "failed": ["server_dlc.py: boom"], "skipped": []},
    )
    monkeypatch.setattr(
        deploy_unified,
        "restart_server",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("restart should not run after upload failure")),
    )
    monkeypatch.setattr(deploy_unified, "restore_remote_backup", lambda backup_path, target: True)

    assert deploy_unified.main() == 1


def test_main_rolls_back_when_health_check_fails(monkeypatch):
    rollback_calls: list[str] = []
    restart_calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server_dlc.py"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, target, label: {
            "ok": True,
            "capacity": {},
            "backup_path": "/opt/dlc-drawing/backups/unit/runtime-before.tgz",
        },
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: {"uploaded": 1, "failed": [], "skipped": []},
    )

    def _restart(target: object, **kwargs: object) -> bool:
        restart_calls.append(bool(kwargs.get("prepare", True)))
        return len(restart_calls) > 1

    monkeypatch.setattr(deploy_unified, "restart_server", _restart)
    monkeypatch.setattr(
        deploy_unified,
        "restore_remote_backup",
        lambda backup_path, target: rollback_calls.append(backup_path) or True,
    )

    assert deploy_unified.main() == 1
    assert rollback_calls == ["/opt/dlc-drawing/backups/unit/runtime-before.tgz"]
    # --files app deploy skips prepare; rollback restart also skips prepare
    assert restart_calls == [False, False]


def test_main_dry_run_does_not_open_remote_preflight(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server_dlc.py", "--dry-run"])
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
    import scripts.deploy_unified_ssh as ssh_mod

    ssh = _RestartSsh()
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)
    monkeypatch.setattr(restart_mod, "HEALTH_GRACE_AFTER_RESTART_S", 0)

    assert deploy_unified.restart_server(target=get_deploy_target("jdcloud")) is True

    assert deploy_unified.HEALTH_WAIT_SECONDS >= 60
    joined = "\n".join(ssh.commands)
    assert "systemctl restart dlc-drawing" in ssh.commands
    assert "systemctl daemon-reload" in ssh.commands
    assert "pkill" not in joined
    assert "nohup" not in joined
    assert ".venv.next" in joined
    assert ".venv.previous" in joined
    assert any(remote.endswith(".service.next") for _, remote in ssh._sftp.put_calls)
    assert any("/health/ready" in command for command in ssh.commands)
    assert any(command.startswith("curl ") for command in ssh.commands)
    assert ssh.closed is True


def test_restart_server_without_prepare_only_restarts_and_polls(monkeypatch):
    import scripts.deploy_unified_restart as restart_mod
    import scripts.deploy_unified_ssh as ssh_mod

    ssh = _RestartSsh()
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)
    monkeypatch.setattr(restart_mod, "HEALTH_GRACE_AFTER_RESTART_S", 0)

    assert deploy_unified.restart_server(target=get_deploy_target("jdcloud"), prepare=False) is True

    joined = "\n".join(ssh.commands)
    assert "systemctl restart dlc-drawing" in ssh.commands
    assert "daemon-reload" not in joined
    assert "pip install" not in joined
    assert ssh._sftp.put_calls == []


def test_should_prepare_runtime_skips_for_app_file_deploys():
    from types import SimpleNamespace

    files_only = SimpleNamespace(files=["routes/device_app_voice_ws.py"], env_update=None)
    with_reqs = SimpleNamespace(files=["requirements_server.txt"], env_update=None)
    slice_mode = SimpleNamespace(files=None, env_update=None)
    with_env = SimpleNamespace(files=["a.py"], env_update="x.env")

    assert deploy_unified._should_prepare_runtime(["routes/device_app_voice_ws.py"], files_only) is False
    assert deploy_unified._should_prepare_runtime(["requirements_server.txt"], with_reqs) is True
    assert deploy_unified._should_prepare_runtime(["server_dlc.py"], slice_mode) is True
    assert deploy_unified._should_prepare_runtime(["a.py"], with_env) is True


def test_prepare_dependencies_soft_fallback_does_not_stamp_hash(monkeypatch):
    import scripts.deploy_unified_restart as restart_mod

    calls: list[str] = []

    def _fake_exec(_ssh: object, command: str, timeout: int = 0) -> tuple[int, str, str]:
        calls.append(command)
        if "pip install" in command:
            return 1, "", "pip network timeout"
        if "import fastapi, uvicorn" in command:
            return 0, "", ""
        if command.startswith("rm -rf"):
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(restart_mod, "_ssh_exec", _fake_exec)
    assert restart_mod._prepare_dependencies(object(), get_deploy_target("jdcloud")) is True
    # Soft-fallback must not write a standalone stamp onto the live .venv.
    stamp_cmds = [
        c for c in calls if "sha256sum" in c and ".venv/.lima-requirements.sha256" in c and "pip install" not in c
    ]
    assert stamp_cmds == []
    assert any(c.startswith("rm -rf") and ".venv.next" in c and "pip install" not in c for c in calls)


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
    import scripts.deploy_unified_preflight as preflight_mod
    import scripts.deploy_unified_ssh as ssh_mod

    ssh = _PrepareSsh()
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)
    monkeypatch.setattr(preflight_mod.time, "strftime", lambda fmt: "20260609_010203")

    result = deploy_unified.prepare_remote_deploy(["server.py"], target=get_deploy_target("jdcloud"), label="unit test")

    assert result["ok"] is True
    assert result["capacity"] == {"disk_free_mb": 2048, "mem_available_mb": 512}
    assert result["backup_path"] == "/opt/dlc-drawing/backups/unit-test-20260609_010203/runtime-before.tgz"
    assert any("df -Pm" in command for command in ssh.commands)
    assert any("tar -czf" in command and "present-files.txt" in command for command in ssh.commands)
    assert any("venv-previous-predeploy" in command for command in ssh.commands)
    assert ssh.closed is True


def test_restore_remote_backup_extracts_tar(monkeypatch):
    import scripts.deploy_unified_preflight as preflight_mod
    import scripts.deploy_unified_ssh as ssh_mod

    ssh = _PrepareSsh()
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: ssh)
    monkeypatch.setattr(ssh_mod, "configure_ssh_host_keys", lambda client: None)

    ok = preflight_mod.restore_remote_backup(
        "/opt/dlc-drawing/backups/unit/runtime-before.tgz", target=get_deploy_target("jdcloud")
    )

    assert ok is True
    assert any("tar -xzf" in command for command in ssh.commands)
    assert any("pre-state.tsv" in command and "systemctl daemon-reload" in command for command in ssh.commands)
    assert ssh.closed is True
