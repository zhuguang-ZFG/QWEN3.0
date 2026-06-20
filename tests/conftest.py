"""Pytest configuration for async test support."""

import sys
from pathlib import Path

import pytest_asyncio  # noqa: F401

# Allow `from tests.xiaozhi_schema import ...` and sibling helper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "xiaozhi_schema"))

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]


def pytest_addoption(parser):
    parser.addoption(
        "--stability-rounds",
        action="store",
        default=0,
        type=int,
        help="Number of stability loop iterations (0 = skip).",
    )
