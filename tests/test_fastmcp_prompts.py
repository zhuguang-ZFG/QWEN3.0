"""Tests for FastMCP prompts — Task 4."""
from __future__ import annotations

from unittest.mock import patch

import pytest

# Check if mcp module is available
try:
    import mcp.server.fastmcp
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="mcp module not installed (install with: pip install 'mcp[cli]')"
)




def test_coding_assistant_prompt_registered():
    """The 'coding-assistant' prompt must be registered."""
    from lima_mcp.fastmcp_server import mcp
    prompts = mcp._prompt_manager.list_prompts()
    names = [p.name for p in prompts]
    assert "coding-assistant" in names


def test_routing_diagnostic_prompt_registered():
    """The 'routing-diagnostic' prompt must be registered."""
    from lima_mcp.fastmcp_server import mcp
    prompts = mcp._prompt_manager.list_prompts()
    names = [p.name for p in prompts]
    assert "routing-diagnostic" in names


def test_coding_assistant_prompt_has_arguments():
    """coding-assistant prompt must accept 'language' and 'task' arguments."""
    from lima_mcp.fastmcp_server import mcp
    prompts = {p.name: p for p in mcp._prompt_manager.list_prompts()}
    prompt = prompts["coding-assistant"]
    arg_names = [a.name for a in prompt.arguments] if prompt.arguments else []
    assert "language" in arg_names
    assert "task" in arg_names


def test_coding_assistant_prompt_returns_messages():
    """Getting coding-assistant prompt returns messages."""
    from lima_mcp.fastmcp_server import coding_assistant_prompt
    result = coding_assistant_prompt(language="python", task="refactor a function")
    # Result could be a list of dicts or PromptMessage objects
    assert len(result) >= 1
    # Check first message has content related to python
    first = result[0]
    if isinstance(first, dict):
        content = first.get("content", "")
    else:
        content = first.content.text if hasattr(first.content, 'text') else str(first.content)
    assert "python" in content.lower() or "Python" in content


def test_routing_diagnostic_prompt_has_arguments():
    """routing-diagnostic prompt must accept 'backend' argument."""
    from lima_mcp.fastmcp_server import mcp
    prompts = {p.name: p for p in mcp._prompt_manager.list_prompts()}
    prompt = prompts["routing-diagnostic"]
    arg_names = [a.name for a in prompt.arguments] if prompt.arguments else []
    assert "backend" in arg_names


def test_routing_diagnostic_prompt_returns_messages():
    """Getting routing-diagnostic prompt returns analysis messages."""
    from lima_mcp.fastmcp_server import routing_diagnostic_prompt

    with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock_health:
        mock_health.return_value = {
            "backends": {"cloudflare": {"status": "degraded"}},
            "overall": "degraded",
        }
        result = routing_diagnostic_prompt(backend="cloudflare")
        assert len(result) >= 1
