"""Regression tests for pyrightconfig.json path sanity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "pyrightconfig.json"


@pytest.fixture
def pyright_config() -> dict:
    assert CONFIG_PATH.is_file(), f"pyright config missing: {CONFIG_PATH}"
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_pyright_include_paths_exist(pyright_config: dict) -> None:
    """Every included file or directory must exist; phantom paths break type checking."""
    for include_path in pyright_config.get("include", []):
        full_path = ROOT / include_path
        assert full_path.exists(), f"pyright include path does not exist: {include_path}"


def test_pyright_no_search_gateway_include(pyright_config: dict) -> None:
    """search_gateway/ was retired and must not be listed as an include path."""
    assert "search_gateway/" not in pyright_config.get("include", [])
