"""Tests for file operation tools (Phase 2.2)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up a safe temp directory for file tool tests
import tempfile

_temp_dir = tempfile.mkdtemp()
os.environ["LIMA_FILE_TOOLS_ROOT"] = _temp_dir

from lima_fc_tools.file_tools import (
    _is_safe_path,
    _list_files,
    _read_file,
    _write_file,
)


def test_safe_path_within_root():
    path = os.path.join(_temp_dir, "test.txt")
    safe, err = _is_safe_path(path)
    assert safe is True
    assert err == ""


def test_unsafe_path_outside_root():
    safe, err = _is_safe_path("/etc/passwd")
    assert safe is False
    assert "outside" in err.lower()


@pytest.mark.asyncio
async def test_write_and_read_file():
    path = os.path.join(_temp_dir, "hello.txt")
    result = await _write_file(path, "Hello, World!")
    assert "error" not in result
    assert result["bytes_written"] == 13

    result = await _read_file(path)
    assert "error" not in result
    assert result["content"] == "Hello, World!"


@pytest.mark.asyncio
async def test_list_files():
    # Create a few files
    await _write_file(os.path.join(_temp_dir, "a.txt"), "aaa")
    await _write_file(os.path.join(_temp_dir, "b.py"), "bbb")

    result = await _list_files(_temp_dir, "*.txt")
    assert "error" not in result
    names = [e["name"] for e in result["entries"]]
    assert "a.txt" in names
    assert "b.py" not in names


@pytest.mark.asyncio
async def test_read_nonexistent_file():
    result = await _read_file(os.path.join(_temp_dir, "nope.txt"))
    assert "error" in result


@pytest.mark.asyncio
async def test_list_nonexistent_dir():
    result = await _list_files("/nonexistent/dir")
    assert "error" in result
