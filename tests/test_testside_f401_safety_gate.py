"""Tests for scripts/testside_f401_safety_gate.py — the test-side F401 safety gate.

These tests validate the gate's pure helpers (parsing pytest collection output,
filtering known-baseline, staged-test filtering) WITHOUT running pytest itself
(which would make the test suite slow and order-dependent). The end-to-end main()
behaviour is covered by a single smoke test that asserts the script returns 0
when only test files staged that pass collection.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "testside_f401_safety_gate.py"

_spec = importlib.util.spec_from_file_location("testside_f401_safety_gate", SCRIPT_PATH)
assert _spec is not None
assert _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
sys.modules["testside_f401_safety_gate"] = gate
_spec.loader.exec_module(gate)

ROOT = gate.ROOT


def test_staged_test_files_filters_non_py_and_non_tests() -> None:
    """Files outside tests/ or non-.py are dropped; only existing tests/*.py kept."""
    paths = [
        ROOT / "tests" / "test_routing_bridge.py",  # existing
        ROOT / "scripts" / "run_pre_commit_check.py",  # not tests/
        ROOT / "tests" / "__init__.py",  # existing
        ROOT / "tests" / "does_not_exist.py",  # missing
        ROOT / "data" / "digital-human" / "wakeword_runtime" / "runtime" / "http_server.py",  # not tests/
    ]
    kept = gate._staged_test_files(paths)
    expected = {ROOT / "tests" / "test_routing_bridge.py", ROOT / "tests" / "__init__.py"}
    assert set(kept) == expected


def test_staged_test_files_accepts_nested_test_subdir() -> None:
    """A tests/<subdir>/<file>.py path is kept."""
    nested = ROOT / "tests" / "device_gateway" / "test_health.py"
    if not nested.exists():
        pytest.skip(f"{nested} not present in this repo state")
    assert nested in gate._staged_test_files([nested])


def test_extract_collect_error_files_parses_error_lines() -> None:
    """Pytest ERROR lines must yield the offending file paths."""
    out = """\
============================= test session starts =============================
collected 5 items

tests/test_a.py ..

ERROR tests/foo/test_bar.py - ImportError: cannot import name 'X' from 'Y'
ERROR tests/test_baz.py - fixture 'lima_client' not found
=========================== short test summary info ===========================
ERROR tests/foo/test_bar.py
ERROR tests/test_baz.py
"""
    failing = gate.extract_collect_error_files(out, baseline=set())
    rel_paths = [p.relative_to(ROOT).as_posix() for p in failing]
    assert "tests/foo/test_bar.py" in rel_paths
    assert "tests/test_baz.py" in rel_paths


def test_extract_collect_error_files_dedupes() -> None:
    """Pytest prints ERROR twice (in progress + summary); only one entry kept."""
    out = "ERROR tests/foo/test_bar.py - ImportError\nERROR tests/foo/test_bar.py\n"
    failing = gate.extract_collect_error_files(out, baseline=set())
    assert len(failing) == 1


def test_extract_collect_error_files_filters_baseline() -> None:
    """Files in the baseline-skip set are NOT reported."""
    out = "ERROR tests/foo/test_bar.py - ImportError\n"
    baseline = {(ROOT / "tests" / "foo" / "test_bar.py").resolve()}
    failing = gate.extract_collect_error_files(out, baseline=baseline)
    assert failing == []


def test_load_baseline_skip_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    """Comments and blank lines in the baseline file are ignored."""
    f = tmp_path / "baseline.txt"
    f.write_text(
        "# comment line\n"
        "\n"
        "tests/foo/test_bar.py\n"
        "  tests/test_baz.py  \n"  # surrounding whitespace should be stripped
        "\n",
        encoding="utf-8",
    )
    skip = gate._load_baseline_skip(str(f))
    assert (ROOT / "tests" / "foo" / "test_bar.py").resolve() in skip
    assert (ROOT / "tests" / "test_baz.py").resolve() in skip
    assert len(skip) == 2


def test_load_baseline_skip_empty_returns_empty() -> None:
    assert gate._load_baseline_skip(None) == set()


def test_normalize_paths_resolves_against_repo_root() -> None:
    """--paths 'tests/test_a.py' becomes an absolute path under the repo root."""
    rel = "tests/test_routing_bridge.py"
    paths = gate._normalize_paths([rel])
    assert paths == [ROOT / "tests" / "test_routing_bridge.py"]


def test_main_returns_zero_when_no_paths_and_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no --paths and stdin is a tty (interactive), main exits 0 with a note."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    rc = gate.main([])  # no --paths
    assert rc == 0


def test_main_no_tests_staged_skips_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """If --paths only names production files, the gate skips collection and returns 0."""
    # Use a real production file (not under tests/), no pytest invocation expected.
    rc = gate.main(["--paths", "scripts/run_pre_commit_check.py"])
    assert rc == 0
