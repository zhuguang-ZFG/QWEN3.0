"""Tests for code execution sandbox (Phase 4.1)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandbox.executor import _docker_available, run_code


def test_docker_available_returns_bool():
    result = _docker_available()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_run_python_code():
    """Run a simple Python expression (uses local fallback if Docker unavailable)."""
    result = await run_code("print(2 + 2)", language="python", timeout=10)
    assert result["exit_code"] == 0
    assert "4" in result["stdout"]
    assert result["language"] == "python"


@pytest.mark.asyncio
async def test_run_javascript_code():
    """Run a simple JavaScript expression."""
    result = await run_code("console.log(2 + 2)", language="javascript", timeout=10)
    assert result["exit_code"] == 0
    assert "4" in result["stdout"]
    assert result["language"] == "javascript"


@pytest.mark.asyncio
async def test_run_shell_code():
    """Run a simple shell command."""
    if os.name == "nt":
        pytest.skip("bash not available on Windows")
    result = await run_code("echo hello", language="shell", timeout=10)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    assert result["language"] == "shell"


@pytest.mark.asyncio
async def test_run_unsupported_language():
    result = await run_code("print('hi')", language="brainfuck", timeout=5)
    assert "error" in result
    assert "Unsupported" in result["error"]


@pytest.mark.asyncio
async def test_run_code_timeout():
    """A long-running script should be killed after timeout."""
    result = await run_code(
        "import time; time.sleep(60)", language="python", timeout=2
    )
    assert result["exit_code"] != 0 or result.get("timeout") is True
    assert result["duration_ms"] < 10000
