"""ReadTracker and SEARCH byte-exact edit gates for workspace sandbox."""

from __future__ import annotations

from agent_runtime.workspace_sandbox import PatchRecord, ReadTracker, WorkspaceSandbox


def test_read_tracker_blocks_unread_edit(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("x = 1\n", encoding="utf-8")

    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=False, enforce_read_gate=True)
    result = sandbox.apply_patches([
        PatchRecord(file_path="main.py", original="x = 1", patched="x = 2"),
    ])
    assert result.ok is False
    assert "not read" in result.error


def test_read_tracker_allows_after_record_read(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("x = 1\n", encoding="utf-8")

    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=False, enforce_read_gate=True)
    sandbox.record_read("main.py")
    result = sandbox.apply_patches([
        PatchRecord(file_path="main.py", original="x = 1", patched="x = 2"),
    ])
    assert result.ok is True


def test_search_block_must_match_bytes(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("hello world\n", encoding="utf-8")

    sandbox = WorkspaceSandbox(root=str(tmp_path), dry_run=False, enforce_read_gate=True)
    sandbox.record_read("main.py")
    result = sandbox.apply_patches([
        PatchRecord(file_path="main.py", original="HELLO", patched="hi"),
    ])
    assert result.ok is False
    assert "SEARCH block not found" in result.error


def test_read_tracker_standalone():
    tracker = ReadTracker()
    assert not tracker.has_read("a.py")
    tracker.record_read("./a.py")
    assert tracker.has_read("a.py")
