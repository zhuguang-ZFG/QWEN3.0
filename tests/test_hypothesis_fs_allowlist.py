"""Hypothesis property tests for lima_mcp.fs_allowlist — path traversal safety."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from lima_mcp.fs_allowlist import is_within_allowed, validate_path


@pytest.fixture(autouse=True)
def _patch_allowed_roots(monkeypatch):
    """Use a temp dir as the sole allowed root for deterministic tests."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LIMA_FILESYSTEM_ALLOWED_ROOTS", tmp)
        # Force reload of the allowed roots cache

        from lima_mcp.fs_allowlist import _load_allowed_roots as _fn
        try:
            _fn.cache_clear()
        except AttributeError:
            pass
        # Create a test file inside the allowed root
        test_file = Path(tmp) / "test.txt"
        test_file.write_text("hello")
        subdir = Path(tmp) / "sub"
        subdir.mkdir(exist_ok=True)
        yield tmp


@given(st.text(alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)), min_size=1, max_size=100))
@settings(max_examples=200)
def test_arbitrary_paths_never_crash_or_bypass(path: str):
    """validate_path should never raise an unhandled exception, and should
    always reject traversal attempts containing '..' as a path component."""
    ok, result = validate_path(path, must_exist=False)

    # Invariant 1: never crashes
    assert isinstance(ok, bool)
    assert isinstance(result, (Path, str))

    # Invariant 2: path traversal always rejected
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        assert not ok, f"traversal not rejected: {path!r}"


@given(st.text(alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)), min_size=1, max_size=150))
@settings(max_examples=200)
def test_arbitrary_paths_for_existing_files(path: str):
    """validate_path with must_exist=True should handle any input gracefully."""
    ok, result = validate_path(path, must_exist=True)
    assert isinstance(ok, bool)
    assert isinstance(result, (Path, str))
    # If it said ok, the path must actually exist
    if ok:
        assert isinstance(result, Path)
        assert result.exists()


def test_rejects_null_byte():
    ok, _ = validate_path("foo\x00bar", must_exist=False)
    assert not ok


def test_rejects_empty():
    ok, _ = validate_path("", must_exist=False)
    assert not ok


def test_rejects_whitespace_only():
    ok, _ = validate_path("   ", must_exist=False)
    assert not ok


def test_rejects_relative_traversal():
    ok, _ = validate_path("../../../etc/passwd", must_exist=False)
    assert not ok


def test_rejects_absolute_traversal(tmp_path):
    """An absolute path outside the allowed root should be rejected."""
    outside = str(tmp_path.parent / "outside.txt")
    ok, _ = validate_path(outside, must_exist=False)
    assert not ok


def test_allows_file_inside_root(_patch_allowed_roots):
    root = _patch_allowed_roots
    ok, result = validate_path(str(Path(root) / "test.txt"), must_exist=True)
    assert ok
    assert isinstance(result, Path)


def test_rejects_nonexistent_file(_patch_allowed_roots):
    root = _patch_allowed_roots
    ok, _ = validate_path(str(Path(root) / "nonexistent.txt"), must_exist=True)
    assert not ok


def test_symlink_not_needed(_patch_allowed_roots):
    """Basic test for is_within_allowed."""
    root = _patch_allowed_roots
    assert is_within_allowed(root)
    assert is_within_allowed(str(Path(root) / "test.txt"))
    assert not is_within_allowed("/etc/passwd")
    assert not is_within_allowed("C:\\Windows\\System32")
