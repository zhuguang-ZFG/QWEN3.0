"""Tests for deploy target selection in the unified deploy script."""

from __future__ import annotations

import sys

from scripts import deploy_unified
from scripts.deploy_unified_common import DeployTarget, get_deploy_target


def _unit_target() -> DeployTarget:
    return get_deploy_target("jdcloud")


def test_main_accepts_target_aliyun(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(sys, "argv", ["deploy_unified.py", "--files", "server.py", "--target", "aliyun"])
    monkeypatch.setattr(
        deploy_unified,
        "prepare_remote_deploy",
        lambda files, target, label: (
            captured.append(f"target={target.name}") or {"ok": True, "capacity": {}, "backup_path": ""}
        ),
    )
    monkeypatch.setattr(
        deploy_unified,
        "deploy_files",
        lambda files, target, dry_run=False: {"uploaded": 0, "failed": [], "skipped": []},
    )

    assert deploy_unified.main() == 0
    assert captured == ["target=aliyun"]


def test_deploy_target_resolution_defaults_to_jdcloud():
    target = get_deploy_target()
    assert target.name == "jdcloud"
    assert target.host == "117.72.118.95"


def test_deploy_target_aliyun():
    target = get_deploy_target("aliyun")
    assert target.name == "aliyun"
    assert target.host == "47.112.162.80"
