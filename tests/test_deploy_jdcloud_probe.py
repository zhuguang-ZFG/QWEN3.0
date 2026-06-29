"""Tests for JDCloud probe deploy helper."""

from __future__ import annotations

from pathlib import Path

from scripts import deploy_jdcloud_probe


def test_collect_probe_files_includes_provider_probe_and_systemd_units():
    project_root = Path(__file__).resolve().parents[1]
    pairs = deploy_jdcloud_probe.collect_probe_files(project_root)

    remotes = {remote for _local, remote in pairs}
    # provider_probe 包内容应在 /opt/lima-probe/provider_probe/ 子目录下
    assert any(remote.startswith("/opt/lima-probe/provider_probe/") for remote in remotes)
    assert "/opt/lima-probe/provider_probe/browser_service.py" in remotes
    assert "/etc/systemd/system/lima-probe-browser.service" in remotes
    assert "/etc/systemd/system/lima-probe.timer" in remotes


def test_main_dry_run_without_ssh(monkeypatch):
    monkeypatch.setattr(
        deploy_jdcloud_probe,
        "upload_probe_files",
        lambda pairs, dry_run=False: len(pairs),
    )
    monkeypatch.setattr(deploy_jdcloud_probe, "restart_probe_services", lambda dry_run=False: True)

    assert deploy_jdcloud_probe.main(["--dry-run"]) == 0
