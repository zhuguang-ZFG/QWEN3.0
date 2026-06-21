"""Tests for the file watcher."""

import time

from code_context.file_watcher import FileWatcher


# ---------------------------------------------------------------------------
# FileWatcher
# ---------------------------------------------------------------------------


class TestFileWatcher:
    def test_detect_new_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, changes = watcher.scan()
        assert len(paths) == 1
        assert changes[0].change_type == "created"

    def test_detect_modified_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()

        time.sleep(0.05)
        (tmp_path / "a.py").write_text("def a():\n    pass")
        paths, changes = watcher.scan()
        assert len(paths) == 1
        assert changes[0].change_type == "modified"

    def test_detect_modified_files_when_mtime_does_not_advance(self, tmp_path, monkeypatch):
        path = tmp_path / "a.py"
        path.write_text("x = 1")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()

        fixed_mtime = watcher.manifest.file_mtimes[str(path)]
        path.write_text("x = 2")
        monkeypatch.setattr("code_context.file_watcher.os.path.getmtime", lambda _path: fixed_mtime)

        paths, changes = watcher.scan()
        assert len(paths) == 1
        assert changes[0].change_type == "modified"

    def test_detect_deleted_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()

        (tmp_path / "a.py").unlink()
        paths, changes = watcher.scan()
        assert any(c.change_type == "deleted" for c in changes)

    def test_ignores_non_python_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.json").write_text("{}")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, _ = watcher.scan()
        assert len(paths) == 0

    def test_includes_typescript(self, tmp_path):
        (tmp_path / "app.ts").write_text("export const x = 1;")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, _ = watcher.scan()
        assert len(paths) == 1

    def test_no_changes_on_rescan(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()
        paths, changes = watcher.scan()
        assert len(paths) == 0
        assert len(changes) == 0
