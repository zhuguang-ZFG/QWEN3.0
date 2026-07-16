"""Unified deploy manifests are tracked, explicit, and runtime-only."""

from pathlib import Path

import pytest

from scripts import deploy_unified
from scripts.deploy_unified_common import (
    _collect_core_files,
    _collect_runtime_files,
    _normalize_deploy_path,
    collect_git_range,
    get_deploy_target,
)

ROOT = Path(__file__).resolve().parents[1]


def test_core_manifest_is_tracked_allowlist() -> None:
    files = _collect_core_files(ROOT)
    assert "server_dlc.py" in files
    assert "requirements_server.txt" in files
    assert "device_voice/asr.py" in files
    assert not any(path.startswith(("tests/", "tmp/", "logs/", "nginx/", "scripts/")) for path in files)
    assert "nginx/nginx.exe" not in files


def test_all_manifest_never_collects_ignored_or_untracked_files(tmp_path) -> None:
    ignored = ROOT / "tmp" / "audit-deploy-secret.log"
    ignored.parent.mkdir(exist_ok=True)
    ignored.write_text("secret", encoding="utf-8")
    try:
        assert "tmp/audit-deploy-secret.log" not in _collect_runtime_files(ROOT)
    finally:
        ignored.unlink(missing_ok=True)


def test_all_manifest_is_the_same_production_allowlist_as_core() -> None:
    assert _collect_runtime_files(ROOT) == _collect_core_files(ROOT)


def test_explicit_non_runtime_file_is_rejected() -> None:
    args = type("Args", (), {"files": ["tests/test_deploy_unified.py"], "slice": "core"})()
    with pytest.raises(ValueError, match="deploy path"):
        deploy_unified._collect_files(args, ROOT)


@pytest.mark.parametrize(
    "path",
    [
        "routes/../../outside.py",
        "../server_dlc.py",
        "/etc/passwd",
        r"C:\\Windows\\system.ini",
        "routes//device_app.py",
        "routes/.hidden.py",
        "routes/bad\x00.py",
        "routes/bad\nname.py",
    ],
)
def test_deploy_path_normalization_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        _normalize_deploy_path(path)


def test_explicit_untracked_core_file_is_rejected() -> None:
    local = ROOT / "routes" / "audit_untracked_deploy.py"
    local.write_text("VALUE = 1\n", encoding="utf-8")
    try:
        args = type("Args", (), {"files": ["routes/audit_untracked_deploy.py"], "slice": "core"})()
        with pytest.raises(ValueError, match="untracked"):
            deploy_unified._collect_files(args, ROOT)
    finally:
        local.unlink(missing_ok=True)


def test_git_range_filters_to_tracked_core_paths(monkeypatch) -> None:
    import scripts.deploy_unified_common as common

    monkeypatch.setattr(common, "_git_tracked_files", lambda root: ["server_dlc.py", "routes/new.py"])

    def _changed(root, before, after, *, diff_filter):
        if diff_filter == "D":
            return ["routes/old.py", "tests/old.py"]
        return ["server_dlc.py", "routes/new.py", "scripts/tool.py", "routes/untracked.py"]

    monkeypatch.setattr(common, "_git_diff_files", _changed)

    uploads, removals = collect_git_range(ROOT, "before", "after")

    assert uploads == ["routes/new.py", "server_dlc.py"]
    assert removals == ["routes/old.py"]


def test_deploy_target_repr_redacts_password() -> None:
    target = get_deploy_target("jdcloud")
    assert "password=" not in repr(target)
    if target.password:
        assert target.password not in repr(target)
