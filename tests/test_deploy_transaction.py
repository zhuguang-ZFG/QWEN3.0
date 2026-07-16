"""Transactional failure and preparation regressions for unified deploy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import deploy_unified
from scripts.deploy_unified_common import get_deploy_target
from tests._deploy_mocks import _PrepareSsh, _RestartSsh, _Stdin, _Stream


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "dry_run": False,
        "no_restart": False,
        "sync_nginx": False,
        "env_update": None,
        "slice": "core",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("failure_kind", ["skipped", "remove", "nginx"])
def test_file_change_failures_restore_backup(monkeypatch, failure_kind: str) -> None:
    restored: list[str] = []
    result = {"uploaded": 1, "failed": [], "skipped": []}
    if failure_kind == "skipped":
        result = {"uploaded": 0, "failed": [], "skipped": ["server_dlc.py"]}
    monkeypatch.setattr(deploy_unified, "deploy_files", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        deploy_unified,
        "remove_remote_files",
        lambda *args, **kwargs: {"removed": 0, "failed": ["remove failed"], "skipped": []},
    )
    monkeypatch.setattr(deploy_unified, "sync_nginx_config", lambda **kwargs: False)
    monkeypatch.setattr(
        deploy_unified,
        "restore_remote_backup",
        lambda backup_path, target: restored.append(backup_path) or True,
    )
    monkeypatch.setattr(deploy_unified, "restart_server", lambda **kwargs: True)
    remove = ["routes/old.py"] if failure_kind == "remove" else []
    args = _args(sync_nginx=failure_kind == "nginx")

    rc = deploy_unified._execute_deploy(
        ["server_dlc.py"], remove, get_deploy_target("jdcloud"), args, "/backup/runtime-before.tgz"
    )

    assert rc == 1
    assert restored == ["/backup/runtime-before.tgz"]


def test_delete_only_deploy_restarts_once_without_upload(monkeypatch) -> None:
    restarts: list[dict[str, object]] = []
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delete-only must not upload")),
    )
    monkeypatch.setattr(
        deploy_unified,
        "remove_remote_files",
        lambda *args, **kwargs: {"removed": 1, "failed": [], "skipped": []},
    )
    monkeypatch.setattr(deploy_unified, "restart_server", lambda **kwargs: restarts.append(kwargs) or True)

    rc = deploy_unified._execute_deploy(
        [], ["routes/old.py"], get_deploy_target("jdcloud"), _args(), "/backup/runtime-before.tgz"
    )

    assert rc == 0
    assert len(restarts) == 1


def test_env_update_uses_append_only_remote_merge(monkeypatch, tmp_path: Path) -> None:
    import scripts.deploy_unified_restart as restart_mod

    update = tmp_path / "deploy.env"
    update.write_text("# comment\nEXISTING=new-value\nNEW_KEY=value with spaces\n", encoding="utf-8")
    ssh = _RestartSsh()

    assert restart_mod._merge_env_update(ssh, get_deploy_target("jdcloud"), update) is True

    payload, remote = ssh._sftp.putfo_calls[0]
    assert payload == b"EXISTING=new-value\nNEW_KEY=value with spaces\n"
    assert remote.endswith("/.env.deploy-update")
    command = ssh.commands[-1]
    assert 'grep -q "^${key}="' in command
    assert "source " not in command
    assert "chmod 0600" in command


def test_empty_backup_output_is_an_explicit_failure(monkeypatch) -> None:
    import scripts.deploy_unified_preflight as preflight_mod

    class EmptyBackupSsh(_PrepareSsh):
        def exec_command(self, command: str):
            if "tar -czf" in command:
                return _Stdin(), _Stream(), _Stream()
            return super().exec_command(command)

    with pytest.raises(RuntimeError, match="no backup path"):
        preflight_mod.create_remote_backup(
            EmptyBackupSsh(), ["server_dlc.py"], target=get_deploy_target("jdcloud"), label="unit"
        )
