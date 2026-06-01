"""Pytest configuration for async test support."""

import pytest_asyncio  # noqa: F401

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]


def pytest_addoption(parser):
    parser.addoption("--stability-rounds", action="store", default=0, type=int,
                     help="Number of stability loop iterations (0 = skip).")


import os

import pytest


@pytest.fixture(autouse=True)
def restore_cwd_after_test():
    cwd = os.getcwd()
    try:
        yield
    finally:
        os.chdir(cwd)
