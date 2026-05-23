"""Pytest configuration for async test support."""

import pytest_asyncio  # noqa: F401

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]
