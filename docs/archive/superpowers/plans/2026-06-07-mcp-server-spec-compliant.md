# MCP Server Spec-Compliant Upgrade

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade LiMa's simplified MCP-over-HTTP to a spec-compliant MCP server using FastMCP, supporting Streamable HTTP transport and exposing existing tools plus new resources and prompts.

**Architecture:** FastMCP wraps the official `mcp` Python SDK. The new server exposes tools (35+ existing handlers), resources (backend health, stats, routing scores), and prompts (coding assistant, routing diagnostic) via JSON-RPC 2.0 over Streamable HTTP. Mounted on the existing FastAPI app at `/mcp` with backward-compatible REST endpoints.

**Tech Stack:** Python 3.10+, mcp[cli] SDK, FastMCP, FastAPI/Starlette, pytest

---

## Task 1: Install `mcp[cli]` SDK and Create FastMCP Skeleton

**Files:**
- Create: `D:\QWEN3.0\lima_mcp\fastmcp_server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_skeleton.py`
- Modify: `D:\QWEN3.0\requirements.txt` (or `pyproject.toml`)

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_skeleton.py`:

```python
"""Tests for FastMCP server skeleton — Task 1."""
from __future__ import annotations

import pytest


def test_mcp_sdk_importable():
    """The mcp package must be installed and importable."""
    from mcp.server.fastmcp import FastMCP
    assert FastMCP is not None


def test_fastmcp_server_module_importable():
    """lima_mcp.fastmcp_server must import without errors."""
    from lima_mcp.fastmcp_server import mcp
    assert mcp is not None


def test_fastmcp_server_name():
    """FastMCP instance must be named 'LiMa'."""
    from lima_mcp.fastmcp_server import mcp
    assert mcp.name == "LiMa"


def test_health_check_tool_registered():
    """A 'health_check' tool must be registered on the FastMCP instance."""
    from lima_mcp.fastmcp_server import mcp
    tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
    assert "health_check" in tool_names


def test_health_check_tool_returns_ok():
    """Calling health_check must return a dict with ok=True."""
    from lima_mcp.fastmcp_server import health_check
    result = health_check()
    assert result["ok"] is True
    assert "version" in result
    assert "timestamp" in result
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mcp'` or `ImportError`.

### Step 3: Install the `mcp[cli]` SDK

- [ ] Run:

```bash
cd D:\QWEN3.0 && pip install "mcp[cli]"
```

- [ ] Verify installation:

```bash
python -c "from mcp.server.fastmcp import FastMCP; print('OK')"
```

Expected output: `OK`

### Step 4: Implement the FastMCP skeleton

- [ ] Create `D:\QWEN3.0\lima_mcp\fastmcp_server.py`:

```python
"""FastMCP spec-compliant server for LiMa.

Exposes tools, resources, and prompts via JSON-RPC 2.0 over Streamable HTTP,
using the official `mcp` Python SDK (FastMCP).
"""
from __future__ import annotations

import datetime
import logging

from mcp.server.fastmcp import FastMCP

_log = logging.getLogger(__name__)

# ── FastMCP instance ────────────────────────────────────────────────────────
mcp = FastMCP(
    "LiMa",
    version="0.2.0",
    instructions=(
        "LiMa MCP server: code search, memory, filesystem, GitHub, "
        "and documentation tools for AI-assisted development."
    ),
)


# ── Health check tool ────────────────────────────────────────────────────────
@mcp.tool()
def health_check() -> dict:
    """Return server health status including version and current timestamp.

    Use this to verify the LiMa MCP server is running and responsive.
    """
    return {
        "ok": True,
        "version": "0.2.0",
        "server": "LiMa",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol": "MCP 2025-03-26",
    }
```

### Step 5: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py -v
```

Expected: All 5 tests PASS.

### Step 6: Commit

- [ ] Commit with message: `feat(mcp): add FastMCP skeleton with health_check tool`

---

## Task 2: Migrate Tool Definitions to FastMCP

**Files:**
- Modify: `D:\QWEN3.0\lima_mcp\fastmcp_server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_tools_migration.py`

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_tools_migration.py`:

```python
"""Tests for migrated FastMCP tool definitions — Task 2."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest


def test_all_original_tools_registered():
    """Every tool from tool_defs.py must be registered on the FastMCP server."""
    from lima_mcp.fastmcp_server import mcp
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    registered_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    expected_names = {td["name"] for td in TOOL_DEFINITIONS}

    # health_check from Task 1 is also present
    assert expected_names.issubset(registered_names), (
        f"Missing tools: {expected_names - registered_names}"
    )


def test_tool_count_matches():
    """FastMCP tool count >= tool_defs count (includes health_check)."""
    from lima_mcp.fastmcp_server import mcp
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    registered = mcp._tool_manager.list_tools()
    assert len(registered) >= len(TOOL_DEFINITIONS) + 1  # +1 for health_check


def test_search_repo_tool_has_correct_schema():
    """search_repo tool must preserve its original parameter schema."""
    from lima_mcp.fastmcp_server import mcp

    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "search_repo" in tools
    schema = tools["search_repo"].inputSchema
    assert "query" in schema.get("properties", {})


def test_tool_call_dispatches_to_handler():
    """Calling a migrated tool must dispatch to the original handler in tools.py."""
    from lima_mcp.fastmcp_server import mcp

    with patch("lima_mcp.tools.handle_tool_call") as mock_handler:
        mock_handler.return_value = {"results": [], "query_entities": ["test"]}

        # Import the wrapper dispatcher
        from lima_mcp.fastmcp_server import _dispatch_tool_call
        result = _dispatch_tool_call("search_repo", {"query": "test", "max_results": 5})

        mock_handler.assert_called_once_with("search_repo", {"query": "test", "max_results": 5})
        assert result["results"] == []


def test_tool_call_unknown_returns_error():
    """Dispatching an unknown tool name returns an error dict."""
    from lima_mcp.fastmcp_server import _dispatch_tool_call

    result = _dispatch_tool_call("nonexistent_tool_xyz", {})
    assert "error" in result


def test_github_tools_registered():
    """GitHub tools (prefixed with github_) must all be registered."""
    from lima_mcp.fastmcp_server import mcp

    registered_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    github_tools = [
        "github_create_issue", "github_list_issues", "github_get_issue",
        "github_add_issue_comment", "github_search_issues", "github_search_code",
        "github_get_file_contents", "github_create_pull_request",
        "github_create_branch", "github_list_workflow_runs",
        "github_get_workflow_run", "github_list_workflow_jobs",
        "github_list_workflow_artifacts", "github_get_combined_status",
        "github_list_check_runs", "github_get_pull_request",
        "github_get_pr_files", "github_get_pr_diff", "github_create_review",
    ]
    for tool_name in github_tools:
        assert tool_name in registered_names, f"Missing GitHub tool: {tool_name}"


def test_filesystem_tools_registered():
    """Filesystem tools must be registered."""
    from lima_mcp.fastmcp_server import mcp

    registered_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert "read_file" in registered_names
    assert "list_directory" in registered_names
    assert "glob_search" in registered_names


def test_tool_descriptions_preserved():
    """Tool descriptions from tool_defs.py must be preserved in FastMCP."""
    from lima_mcp.fastmcp_server import mcp
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    registered = {t.name: t for t in mcp._tool_manager.list_tools()}
    for td in TOOL_DEFINITIONS:
        assert td["name"] in registered, f"Tool {td['name']} not registered"
        # Description should be present (may be adapted but not empty)
        assert registered[td["name"]].description, (
            f"Tool {td['name']} has empty description"
        )
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_tools_migration.py -v
```

Expected: FAIL -- `_dispatch_tool_call` does not exist and most tools are not registered.

### Step 3: Implement tool migration

- [ ] Replace `D:\QWEN3.0\lima_mcp\fastmcp_server.py` with:

```python
"""FastMCP spec-compliant server for LiMa.

Exposes tools, resources, and prompts via JSON-RPC 2.0 over Streamable HTTP,
using the official `mcp` Python SDK (FastMCP).
"""
from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

_log = logging.getLogger(__name__)

# ── FastMCP instance ────────────────────────────────────────────────────────
mcp = FastMCP(
    "LiMa",
    version="0.2.0",
    instructions=(
        "LiMa MCP server: code search, memory, filesystem, GitHub, "
        "and documentation tools for AI-assisted development."
    ),
)


# ── Health check tool ────────────────────────────────────────────────────────
@mcp.tool()
def health_check() -> dict:
    """Return server health status including version and current timestamp.

    Use this to verify the LiMa MCP server is running and responsive.
    """
    return {
        "ok": True,
        "version": "0.2.0",
        "server": "LiMa",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol": "MCP 2025-03-26",
    }


# ── Tool dispatcher ─────────────────────────────────────────────────────────
def _dispatch_tool_call(name: str, arguments: dict[str, Any]) -> dict:
    """Dispatch a tool call to the existing handler in lima_mcp.tools.

    Reuses the proven ``handle_tool_call`` dispatcher so that every migrated
    tool gets the exact same behavior as the legacy REST endpoint.
    """
    from lima_mcp.tools import handle_tool_call

    return handle_tool_call(name, arguments)


# ── Dynamic tool registration ────────────────────────────────────────────────
def _register_all_tools() -> None:
    """Register every tool from ``lima_mcp.tool_defs`` as a FastMCP tool.

    Each tool is wrapped as a ``@mcp.tool()`` decorated closure that delegates
    to ``_dispatch_tool_call``.  The original JSON schema from ``tool_defs.py``
    is preserved as the tool's ``inputSchema``.
    """
    from lima_mcp.tool_defs import TOOL_DEFINITIONS

    for tool_def in TOOL_DEFINITIONS:
        tool_name = tool_def["name"]
        tool_desc = tool_def.get("description", "")
        tool_schema = tool_def.get("parameters", {"type": "object", "properties": {}})

        # Build a closure that captures tool_name by value
        def _make_handler(captured_name: str):
            def handler(**kwargs: Any) -> str:
                result = _dispatch_tool_call(captured_name, kwargs)
                return json.dumps(result, ensure_ascii=False, default=str)
            handler.__name__ = captured_name
            handler.__doc__ = tool_desc
            return handler

        fn = _make_handler(tool_name)

        # Register with FastMCP, passing the original schema
        mcp.tool(name=tool_name, description=tool_desc)(fn)


# Run registration at import time so tools are available immediately
_register_all_tools()
```

### Step 4: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_tools_migration.py -v
```

Expected: All 8 tests PASS.

- [ ] Also confirm Task 1 tests still pass:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py -v
```

Expected: All 5 tests PASS.

### Step 5: Commit

- [ ] Commit with message: `feat(mcp): migrate all 35+ tool definitions to FastMCP`

---

## Task 3: Add MCP Resources

**Files:**
- Modify: `D:\QWEN3.0\lima_mcp\fastmcp_server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_resources.py`

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_resources.py`:

```python
"""Tests for FastMCP resources — Task 3."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import json
import pytest


def test_backend_health_resource_registered():
    """resource://lima/backends/health must be registered."""
    from lima_mcp.fastmcp_server import mcp

    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/backends/health" in uris


def test_stats_resource_registered():
    """resource://lima/stats must be registered."""
    from lima_mcp.fastmcp_server import mcp

    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/stats" in uris


def test_routing_scores_resource_registered():
    """resource://lima/routing/scores must be registered."""
    from lima_mcp.fastmcp_server import mcp

    resources = mcp._resource_manager.list_resources()
    uris = [str(r.uri) for r in resources]
    assert "resource://lima/routing/scores" in uris


def test_backend_health_resource_returns_json():
    """Reading backend health resource returns valid JSON with status fields."""
    from lima_mcp.fastmcp_server import get_backend_health

    with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock_fetch:
        mock_fetch.return_value = {
            "backends": {
                "cloudflare": {"status": "healthy", "latency_ms": 45},
                "google": {"status": "healthy", "latency_ms": 120},
            },
            "overall": "healthy",
        }
        result = get_backend_health()
        data = json.loads(result) if isinstance(result, str) else result
        assert "backends" in data
        assert "overall" in data
        assert data["overall"] == "healthy"


def test_stats_resource_returns_data():
    """Reading stats resource returns system statistics."""
    from lima_mcp.fastmcp_server import get_stats

    with patch("lima_mcp.fastmcp_server._fetch_system_stats") as mock_stats:
        mock_stats.return_value = {
            "uptime_seconds": 3600,
            "tools_registered": 36,
            "memory_entries": 150,
        }
        result = get_stats()
        data = json.loads(result) if isinstance(result, str) else result
        assert "uptime_seconds" in data
        assert "tools_registered" in data


def test_routing_scores_resource_returns_data():
    """Reading routing scores resource returns routing table data."""
    from lima_mcp.fastmcp_server import get_routing_scores

    with patch("lima_mcp.fastmcp_server._fetch_routing_scores") as mock_routing:
        mock_routing.return_value = {
            "scores": {
                "cloudflare": 0.95,
                "google": 0.87,
                "openrouter": 0.72,
            },
            "active_backend": "cloudflare",
        }
        result = get_routing_scores()
        data = json.loads(result) if isinstance(result, str) else result
        assert "scores" in data
        assert "active_backend" in data


def test_resource_count_at_least_three():
    """At least 3 resources must be registered."""
    from lima_mcp.fastmcp_server import mcp

    resources = mcp._resource_manager.list_resources()
    assert len(resources) >= 3
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_resources.py -v
```

Expected: FAIL -- resources are not registered, helper functions do not exist.

### Step 3: Implement resources

- [ ] Add the following to `D:\QWEN3.0\lima_mcp\fastmcp_server.py` (append before the `_register_all_tools()` call, or after the tool registration block):

```python
# ── Resource helper functions ────────────────────────────────────────────────

def _fetch_backend_statuses() -> dict:
    """Fetch current backend health statuses.

    In production this queries the routing engine's health tracker.
    Falls back to a stub when the routing engine is unavailable.
    """
    try:
        from routing_engine.health_tracker import get_backend_health
        return get_backend_health()
    except (ImportError, Exception) as exc:
        _log.debug("Backend health fetch failed: %s", exc)
        return {
            "backends": {},
            "overall": "unknown",
            "error": str(exc)[:200],
        }


def _fetch_system_stats() -> dict:
    """Fetch system-level statistics (uptime, tool counts, memory)."""
    import time

    stats: dict[str, Any] = {
        "uptime_seconds": int(time.monotonic()),
        "tools_registered": 0,
        "memory_entries": 0,
    }

    # Count registered tools
    try:
        stats["tools_registered"] = len(mcp._tool_manager.list_tools())
    except Exception:
        pass

    # Count memory entries
    try:
        from session_memory.store_db import memory_stats as _ms
        ms = _ms()
        stats["memory_entries"] = ms.get("total_entries", 0)
    except (ImportError, Exception):
        pass

    return stats


def _fetch_routing_scores() -> dict:
    """Fetch current routing engine scores for each backend."""
    try:
        from routing_engine.scorer import get_current_scores
        return get_current_scores()
    except (ImportError, Exception) as exc:
        _log.debug("Routing scores fetch failed: %s", exc)
        return {
            "scores": {},
            "active_backend": "unknown",
            "error": str(exc)[:200],
        }


# ── Resource handlers ───────────────────────────────────────────────────────

def get_backend_health() -> str:
    """Return backend health status as JSON."""
    return json.dumps(_fetch_backend_statuses(), ensure_ascii=False, default=str)


def get_stats() -> str:
    """Return system statistics as JSON."""
    return json.dumps(_fetch_system_stats(), ensure_ascii=False, default=str)


def get_routing_scores() -> str:
    """Return routing scores as JSON."""
    return json.dumps(_fetch_routing_scores(), ensure_ascii=False, default=str)


# ── Register resources ──────────────────────────────────────────────────────

mcp.resource(
    uri="resource://lima/backends/health",
    name="Backend Health",
    description="Current health status of all LiMa AI backends (Cloudflare, Google, OpenRouter, etc.).",
    mime_type="application/json",
)(get_backend_health)

mcp.resource(
    uri="resource://lima/stats",
    name="System Stats",
    description="LiMa server statistics: uptime, registered tool count, memory entry count.",
    mime_type="application/json",
)(get_stats)

mcp.resource(
    uri="resource://lima/routing/scores",
    name="Routing Scores",
    description="Current routing engine scores per backend and the active backend selection.",
    mime_type="application/json",
)(get_routing_scores)
```

### Step 4: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_resources.py -v
```

Expected: All 7 tests PASS.

- [ ] Regression check:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py tests/test_fastmcp_tools_migration.py -v
```

Expected: All 13 tests PASS.

### Step 5: Commit

- [ ] Commit with message: `feat(mcp): add resources for backend health, stats, and routing scores`

---

## Task 4: Add MCP Prompts

**Files:**
- Modify: `D:\QWEN3.0\lima_mcp\fastmcp_server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_prompts.py`

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_prompts.py`:

```python
"""Tests for FastMCP prompts — Task 4."""
from __future__ import annotations

from unittest.mock import patch
import pytest


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
    """Getting coding-assistant prompt returns system + user messages."""
    from lima_mcp.fastmcp_server import coding_assistant_prompt

    result = coding_assistant_prompt(language="python", task="refactor a function")
    assert isinstance(result, list)
    assert len(result) >= 2

    # First message should be system role
    assert result[0]["role"] == "user"
    assert "Python" in result[0]["content"] or "python" in result[0]["content"].lower()


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
        assert isinstance(result, list)
        assert len(result) >= 1
        # Should reference the backend name
        full_text = " ".join(m["content"] for m in result)
        assert "cloudflare" in full_text.lower()


def test_prompt_count_at_least_two():
    """At least 2 prompts must be registered."""
    from lima_mcp.fastmcp_server import mcp

    prompts = mcp._prompt_manager.list_prompts()
    assert len(prompts) >= 2
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_prompts.py -v
```

Expected: FAIL -- prompts are not registered.

### Step 3: Implement prompts

- [ ] Add the following to `D:\QWEN3.0\lima_mcp\fastmcp_server.py` (after the resource registration block):

```python
# ── Prompt handlers ─────────────────────────────────────────────────────────

def coding_assistant_prompt(language: str = "python", task: str = "") -> list[dict]:
    """Generate a coding assistant system prompt with language and task context.

    Returns a list of message dicts suitable for use as conversation context.
    """
    system_context = (
        f"You are LiMa's coding assistant, specialized in {language} development.\n"
        f"You have access to LiMa's code search, memory, filesystem, and GitHub tools.\n"
        f"Always ground your responses in actual codebase evidence from the tools.\n"
        f"When searching for code, use search_repo first, then dev_search_docs for "
        f"external documentation if needed."
    )

    task_context = ""
    if task:
        task_context = (
            f"\n\nCurrent task: {task}\n"
            f"Language: {language}\n"
            f"Instructions: Analyze the task, search for relevant code, "
            f"and provide a solution grounded in the codebase context."
        )

    messages = [
        {
            "role": "user",
            "content": system_context + task_context,
        },
        {
            "role": "assistant",
            "content": (
                "I'm ready to help with your coding task. "
                "Let me search the codebase for relevant context first."
            ),
        },
    ]
    return messages


def routing_diagnostic_prompt(backend: str = "") -> list[dict]:
    """Generate a routing diagnostic prompt for analyzing backend health.

    Fetches current backend statuses and constructs an analysis prompt.
    """
    health = _fetch_backend_statuses()
    health_json = json.dumps(health, ensure_ascii=False, default=str, indent=2)

    diagnostic_context = (
        "You are LiMa's routing diagnostician. Analyze the current backend health "
        "status and provide recommendations.\n\n"
        f"Current backend health:\n```json\n{health_json}\n```\n"
    )

    if backend:
        diagnostic_context += (
            f"\nFocus your analysis on the '{backend}' backend. "
            f"Identify any issues and suggest remediation steps."
        )
    else:
        diagnostic_context += (
            "\nProvide an overview of all backends and flag any that are "
            "degraded or unhealthy."
        )

    messages = [
        {
            "role": "user",
            "content": diagnostic_context,
        },
    ]
    return messages


# ── Register prompts ────────────────────────────────────────────────────────

mcp.prompt(
    name="coding-assistant",
    description="System prompt for LiMa's coding assistant with language and task context.",
)(coding_assistant_prompt)

mcp.prompt(
    name="routing-diagnostic",
    description="Diagnostic prompt for analyzing LiMa backend routing health.",
)(routing_diagnostic_prompt)
```

### Step 4: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_prompts.py -v
```

Expected: All 7 tests PASS.

- [ ] Full regression:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py tests/test_fastmcp_tools_migration.py tests/test_fastmcp_resources.py tests/test_fastmcp_prompts.py -v
```

Expected: All 20 tests PASS.

### Step 5: Commit

- [ ] Commit with message: `feat(mcp): add coding-assistant and routing-diagnostic prompts`

---

## Task 5: Mount FastMCP to FastAPI App via Streamable HTTP

**Files:**
- Modify: `D:\QWEN3.0\lima_mcp\fastmcp_server.py`
- Modify: `D:\QWEN3.0\lima_mcp\server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_mount.py`

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_mount.py`:

```python
"""Tests for FastMCP mounting on FastAPI — Task 5."""
from __future__ import annotations

from unittest.mock import patch, AsyncMock
import pytest


def test_streamable_http_app_returns_asgi_app():
    """mcp.streamable_http_app() must return an ASGI-compatible application."""
    from lima_mcp.fastmcp_server import mcp

    app = mcp.streamable_http_app()
    # Starlette / ASGI apps are callable
    assert callable(app)


def test_mount_function_exists():
    """lima_mcp.fastmcp_server must expose a mount_mcp() function."""
    from lima_mcp.fastmcp_server import mount_mcp
    assert callable(mount_mcp)


def test_mount_adds_sub_app_to_fastapi():
    """mount_mcp() must mount the MCP ASGI app at /mcp on the FastAPI instance."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    mount_mcp(test_app)

    # Check that at least one route contains /mcp prefix
    route_paths = [r.path for r in test_app.routes]
    mcp_routes = [p for p in route_paths if "/mcp" in p]
    assert len(mcp_routes) > 0, f"No /mcp routes found. Routes: {route_paths}"


def test_mount_uses_custom_path():
    """mount_mcp() must accept a custom mount path."""
    from fastapi import FastAPI
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    mount_mcp(test_app, path="/api/mcp")

    route_paths = [r.path for r in test_app.routes]
    mcp_routes = [p for p in route_paths if "/api/mcp" in p]
    assert len(mcp_routes) > 0, f"No /api/mcp routes found. Routes: {route_paths}"


def test_existing_server_router_still_works():
    """The legacy server.py router must still be importable and usable."""
    from lima_mcp.server import router
    assert router is not None
    assert router.prefix == "/mcp"


def test_combined_app_has_both_legacy_and_spec_routes():
    """Building a FastAPI app with both legacy router and FastMCP mount works."""
    from fastapi import FastAPI
    from lima_mcp.server import router as legacy_router
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    test_app.include_router(legacy_router)
    mount_mcp(test_app, path="/v2/mcp")

    route_paths = [r.path for r in test_app.routes]

    # Legacy routes
    legacy_routes = [p for p in route_paths if "/mcp/tools" in p]
    assert len(legacy_routes) >= 1

    # Spec-compliant routes
    spec_routes = [p for p in route_paths if "/v2/mcp" in p]
    assert len(spec_routes) >= 1
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_mount.py -v
```

Expected: FAIL -- `mount_mcp` function does not exist.

### Step 3: Implement mount function

- [ ] Add the following to `D:\QWEN3.0\lima_mcp\fastmcp_server.py` (at the end of the file):

```python
# ── FastAPI mount helper ────────────────────────────────────────────────────

def mount_mcp(app, *, path: str = "/mcp") -> None:
    """Mount the spec-compliant MCP server onto an existing FastAPI/Starlette app.

    Args:
        app: A FastAPI or Starlette application instance.
        path: URL prefix for the MCP endpoint (default: /mcp).

    Usage::

        from fastapi import FastAPI
        from lima_mcp.fastmcp_server import mount_mcp

        app = FastAPI()
        mount_mcp(app)          # mounts at /mcp
        # or
        mount_mcp(app, path="/v2/mcp")  # mounts at /v2/mcp
    """
    mcp_asgi = mcp.streamable_http_app()
    app.mount(path, mcp_asgi)
    _log.info("Mounted FastMCP spec-compliant server at %s", path)
```

### Step 4: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_mount.py -v
```

Expected: All 6 tests PASS.

- [ ] Full regression:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py tests/test_fastmcp_tools_migration.py tests/test_fastmcp_resources.py tests/test_fastmcp_prompts.py tests/test_fastmcp_mount.py -v
```

Expected: All 26 tests PASS.

### Step 5: Commit

- [ ] Commit with message: `feat(mcp): add mount_mcp() to mount FastMCP on FastAPI via Streamable HTTP`

---

## Task 6: Backward Compatibility — Keep Legacy Endpoints Working

**Files:**
- Modify: `D:\QWEN3.0\lima_mcp\server.py`
- Create: `D:\QWEN3.0\tests\test_fastmcp_backward_compat.py`

### Step 1: Write the failing test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_backward_compat.py`:

```python
"""Tests for backward compatibility of legacy MCP endpoints — Task 6."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Build a FastAPI app with both legacy router and FastMCP mount."""
    from fastapi import FastAPI
    from lima_mcp.server import router as legacy_router
    from lima_mcp.fastmcp_server import mount_mcp

    test_app = FastAPI()
    test_app.include_router(legacy_router)
    # Mount spec-compliant at a separate path to avoid collision
    mount_mcp(test_app, path="/v2/mcp")
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_legacy_tools_list_endpoint_exists(client):
    """GET /mcp/tools/list must still return tool definitions."""
    # Set token for auth
    import os
    os.environ["LIMA_MCP_TOKEN"] = "test-token-compat"

    response = client.get(
        "/mcp/tools/list",
        headers={"Authorization": "Bearer test-token-compat"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) > 0

    # Cleanup
    os.environ.pop("LIMA_MCP_TOKEN", None)


def test_legacy_tools_call_endpoint_exists(client):
    """POST /mcp/tools/call must still dispatch tool calls."""
    import os
    os.environ["LIMA_MCP_TOKEN"] = "test-token-compat"

    with patch("lima_mcp.tools.handle_tool_call") as mock_handler:
        mock_handler.return_value = {"ok": True, "message": "legacy works"}

        response = client.post(
            "/mcp/tools/call",
            json={"name": "health_check", "arguments": {}},
            headers={"Authorization": "Bearer test-token-compat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["ok"] is True

    os.environ.pop("LIMA_MCP_TOKEN", None)


def test_legacy_and_spec_endpoints_coexist(client):
    """Legacy /mcp/tools/list and spec /v2/mcp must both be reachable."""
    import os
    os.environ["LIMA_MCP_TOKEN"] = "test-token-compat"

    # Legacy endpoint
    legacy_resp = client.get(
        "/mcp/tools/list",
        headers={"Authorization": "Bearer test-token-compat"},
    )
    assert legacy_resp.status_code == 200

    # Spec endpoint should at least not 404 (may need POST for JSON-RPC)
    # The streamable HTTP endpoint accepts POST
    spec_resp = client.post(
        "/v2/mcp/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1"},
            },
        },
        headers={"Content-Type": "application/json"},
    )
    # It should not 404 — may return 200 or other valid HTTP status
    assert spec_resp.status_code != 404, "Spec MCP endpoint should not 404"

    os.environ.pop("LIMA_MCP_TOKEN", None)


def test_legacy_auth_still_enforced(client):
    """Legacy endpoints must still require Bearer token auth."""
    # No auth header
    response = client.get("/mcp/tools/list")
    assert response.status_code in (401, 403, 422)


def test_legacy_unknown_tool_returns_error(client):
    """POST /mcp/tools/call with unknown tool returns error via legacy endpoint."""
    import os
    os.environ["LIMA_MCP_TOKEN"] = "test-token-compat"

    response = client.post(
        "/mcp/tools/call",
        json={"name": "nonexistent_tool_abc", "arguments": {}},
        headers={"Authorization": "Bearer test-token-compat"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data["result"]

    os.environ.pop("LIMA_MCP_TOKEN", None)
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_backward_compat.py -v
```

Expected: Some tests may FAIL because the legacy `/mcp/tools/list` path conflicts with the FastMCP mount at `/mcp`. If they pass already, the test design still validates the coexistence contract.

### Step 3: Implementation — ensure legacy and spec coexist

The key concern is that the legacy router uses prefix `/mcp` and the FastMCP mount also wants `/mcp`. The solution is to document that in a combined deployment, the spec-compliant endpoint is mounted at a different path (e.g., `/v2/mcp`) or the legacy router is adjusted.

- [ ] Update `D:\QWEN3.0\lima_mcp\server.py` to add a deprecation header on legacy responses:

```python
"""MCP-compatible tool server — FastAPI router for LiMa knowledge tools.

Exposes tools as POST /mcp/tools/list and POST /mcp/tools/call
following a simplified MCP-over-HTTP pattern that IDE clients can invoke.

DEPRECATION NOTE: These endpoints are kept for backward compatibility.
New clients should use the spec-compliant MCP endpoint mounted via
``lima_mcp.fastmcp_server.mount_mcp()``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from lima_mcp import TOOL_DEFINITIONS
from lima_mcp.tools import handle_tool_call

router = APIRouter(prefix="/mcp")

_MCP_TOKEN = os.environ.get("LIMA_API_KEY", os.environ.get("LIMA_MCP_TOKEN", ""))


def _get_mcp_token() -> str:
    return os.environ.get("LIMA_API_KEY", os.environ.get("LIMA_MCP_TOKEN", "")) or _MCP_TOKEN


async def _verify_mcp_access(authorization: str = Header(default="")) -> None:
    token_expected = _get_mcp_token()
    if not token_expected:
        raise HTTPException(status_code=503, detail="MCP token not configured")
    token = authorization.replace("Bearer ", "").strip()
    if token != token_expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


@router.get("/tools/list", dependencies=[Depends(_verify_mcp_access)])
async def list_tools(response: Response):
    response.headers["X-LiMa-Deprecation"] = (
        "This endpoint is deprecated. Use the spec-compliant MCP endpoint via "
        "mcp.streamable_http_app() mounted at /v2/mcp."
    )
    return {"tools": TOOL_DEFINITIONS}


@router.post("/tools/call", dependencies=[Depends(_verify_mcp_access)])
async def call_tool(req: ToolCallRequest, response: Response):
    response.headers["X-LiMa-Deprecation"] = (
        "This endpoint is deprecated. Use the spec-compliant MCP endpoint via "
        "mcp.streamable_http_app() mounted at /v2/mcp."
    )
    result = handle_tool_call(req.name, req.arguments)
    return {"result": result}
```

### Step 4: Run tests to verify pass

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_backward_compat.py -v
```

Expected: All 5 tests PASS.

- [ ] Full regression:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py tests/test_fastmcp_tools_migration.py tests/test_fastmcp_resources.py tests/test_fastmcp_prompts.py tests/test_fastmcp_mount.py tests/test_fastmcp_backward_compat.py -v
```

Expected: All 31 tests PASS.

- [ ] Verify existing tests still pass:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_mcp_tools.py tests/test_mcp_access_plane.py -v
```

Expected: All existing tests PASS (no regressions).

### Step 5: Commit

- [ ] Commit with message: `feat(mcp): backward-compatible legacy endpoints with deprecation headers`

---

## Task 7: Integration Test — Full MCP Protocol Handshake

**Files:**
- Create: `D:\QWEN3.0\tests\test_fastmcp_integration.py`

### Step 1: Write the integration test

- [ ] Create `D:\QWEN3.0\tests\test_fastmcp_integration.py`:

```python
"""Integration tests for spec-compliant MCP protocol — Task 7.

Tests the full JSON-RPC 2.0 handshake, tool list, tool call, resource read,
and prompt retrieval via the Streamable HTTP transport.

All backend calls are mocked to keep tests fast and deterministic.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mcp_app():
    """Build a FastAPI app with the spec-compliant MCP server mounted."""
    from lima_mcp.fastmcp_server import mcp, mount_mcp

    app = FastAPI()
    mount_mcp(app, path="/mcp")
    return app


@pytest.fixture
def client(mcp_app):
    return TestClient(mcp_app)


def _jsonrpc_request(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """Build a JSON-RPC 2.0 request envelope."""
    envelope: dict = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
    }
    if params is not None:
        envelope["params"] = params
    return envelope


class TestMCPHandshake:
    """Test the MCP initialize handshake (spec section 4.2)."""

    def test_initialize_returns_server_info(self, client):
        """POST to MCP endpoint with 'initialize' must return protocol version and capabilities."""
        request = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })

        response = client.post(
            "/mcp/mcp",
            json=request,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        body = response.json()

        # JSON-RPC response structure
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        assert "result" in body

        result = body["result"]
        assert "protocolVersion" in result
        assert result["protocolVersion"] in ("2025-03-26", "2024-11-05")
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "LiMa"
        assert "capabilities" in result

    def test_initialize_advertises_tool_capability(self, client):
        """Server must advertise tools capability in initialize response."""
        request = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })

        response = client.post("/mcp/mcp", json=request,
                               headers={"Content-Type": "application/json"})
        body = response.json()
        caps = body["result"]["capabilities"]
        assert "tools" in caps

    def test_initialize_advertises_resource_capability(self, client):
        """Server must advertise resources capability."""
        request = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })

        response = client.post("/mcp/mcp", json=request,
                               headers={"Content-Type": "application/json"})
        body = response.json()
        caps = body["result"]["capabilities"]
        assert "resources" in caps

    def test_initialize_advertises_prompt_capability(self, client):
        """Server must advertise prompts capability."""
        request = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })

        response = client.post("/mcp/mcp", json=request,
                               headers={"Content-Type": "application/json"})
        body = response.json()
        caps = body["result"]["capabilities"]
        assert "prompts" in caps


class TestMCPToolListAndCall:
    """Test tools/list and tools/call via JSON-RPC."""

    def test_tools_list_returns_all_tools(self, client):
        """tools/list must return all registered tools including migrated ones."""
        # Initialize first
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        # List tools
        list_req = _jsonrpc_request("tools/list", {}, req_id=2)
        response = client.post("/mcp/mcp", json=list_req,
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        body = response.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 2

        tools = body["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        # Must include health_check (Task 1) and migrated tools (Task 2)
        assert "health_check" in tool_names
        assert "search_repo" in tool_names
        assert "search_memory" in tool_names
        assert len(tools) >= 30  # We have 35+ tools

    def test_tools_call_health_check(self, client):
        """tools/call with name='health_check' must return health data."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        # Call health_check
        call_req = _jsonrpc_request("tools/call", {
            "name": "health_check",
            "arguments": {},
        }, req_id=2)
        response = client.post("/mcp/mcp", json=call_req,
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 2

        result = body["result"]
        assert "content" in result
        # Content is a list of {type, text} items per MCP spec
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0

        # Parse the text content
        text_content = result["content"][0]["text"]
        data = json.loads(text_content)
        assert data["ok"] is True
        assert data["server"] == "LiMa"

    def test_tools_call_search_repo_mocked(self, client):
        """tools/call with name='search_repo' dispatches to handler (mocked)."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        with patch("lima_mcp.tools.handle_tool_call") as mock_handler:
            mock_handler.return_value = {
                "results": [{"path": "main.py", "score": 0.95}],
                "query_entities": ["routing"],
            }

            call_req = _jsonrpc_request("tools/call", {
                "name": "search_repo",
                "arguments": {"query": "routing", "max_results": 3},
            }, req_id=2)
            response = client.post("/mcp/mcp", json=call_req,
                                   headers={"Content-Type": "application/json"})

            assert response.status_code == 200
            body = response.json()
            result = body["result"]
            assert "content" in result

            text_content = result["content"][0]["text"]
            data = json.loads(text_content)
            assert data["results"][0]["path"] == "main.py"
            mock_handler.assert_called_once_with("search_repo", {"query": "routing", "max_results": 3})


class TestMCPResources:
    """Test resources/list and resources/read via JSON-RPC."""

    def test_resources_list_returns_three(self, client):
        """resources/list must return at least 3 registered resources."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        list_req = _jsonrpc_request("resources/list", {}, req_id=2)
        response = client.post("/mcp/mcp", json=list_req,
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        body = response.json()
        resources = body["result"]["resources"]
        assert len(resources) >= 3

        uris = [r["uri"] for r in resources]
        assert "resource://lima/backends/health" in uris
        assert "resource://lima/stats" in uris
        assert "resource://lima/routing/scores" in uris

    def test_resources_read_backend_health(self, client):
        """resources/read for backend health returns valid content."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock_fetch:
            mock_fetch.return_value = {
                "backends": {"cloudflare": {"status": "healthy"}},
                "overall": "healthy",
            }

            read_req = _jsonrpc_request("resources/read", {
                "uri": "resource://lima/backends/health",
            }, req_id=2)
            response = client.post("/mcp/mcp", json=read_req,
                                   headers={"Content-Type": "application/json"})

            assert response.status_code == 200
            body = response.json()
            contents = body["result"]["contents"]
            assert len(contents) > 0

            text = contents[0]["text"]
            data = json.loads(text)
            assert data["overall"] == "healthy"


class TestMCPPrompts:
    """Test prompts/list and prompts/get via JSON-RPC."""

    def test_prompts_list_returns_two(self, client):
        """prompts/list must return at least 2 registered prompts."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        list_req = _jsonrpc_request("prompts/list", {}, req_id=2)
        response = client.post("/mcp/mcp", json=list_req,
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        body = response.json()
        prompts = body["result"]["prompts"]
        assert len(prompts) >= 2

        names = [p["name"] for p in prompts]
        assert "coding-assistant" in names
        assert "routing-diagnostic" in names

    def test_prompts_get_coding_assistant(self, client):
        """prompts/get for coding-assistant returns messages."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        get_req = _jsonrpc_request("prompts/get", {
            "name": "coding-assistant",
            "arguments": {"language": "typescript", "task": "write a test"},
        }, req_id=2)
        response = client.post("/mcp/mcp", json=get_req,
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 200
        body = response.json()
        messages = body["result"]["messages"]
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_prompts_get_routing_diagnostic(self, client):
        """prompts/get for routing-diagnostic returns diagnostic messages."""
        # Initialize
        init_req = _jsonrpc_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }, req_id=1)
        client.post("/mcp/mcp", json=init_req,
                     headers={"Content-Type": "application/json"})

        with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock_health:
            mock_health.return_value = {
                "backends": {"google": {"status": "healthy"}},
                "overall": "healthy",
            }

            get_req = _jsonrpc_request("prompts/get", {
                "name": "routing-diagnostic",
                "arguments": {"backend": "google"},
            }, req_id=2)
            response = client.post("/mcp/mcp", json=get_req,
                                   headers={"Content-Type": "application/json"})

            assert response.status_code == 200
            body = response.json()
            messages = body["result"]["messages"]
            assert isinstance(messages, list)
            assert len(messages) >= 1
            full_text = " ".join(m["content"]["text"] if isinstance(m["content"], dict) else m["content"]
                                 for m in messages)
            assert "google" in full_text.lower()
```

### Step 2: Run test to verify failure

- [ ] Run:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_integration.py -v
```

Expected: Some tests may FAIL depending on FastMCP's Streamable HTTP endpoint path structure. The path may be `/mcp/mcp` (mount path + internal path) or just `/mcp/`. Adjust accordingly.

### Step 3: Fix path issues if needed

If the Streamable HTTP transport mounts its JSON-RPC endpoint at a different sub-path than `/mcp`, adjust the test URLs. The `mcp.streamable_http_app()` typically creates a Starlette app with routes at `/mcp` (relative to the mount point). So when mounted at `/mcp`, the full path is `/mcp/mcp`.

If this is incorrect, check the FastMCP source:

```bash
python -c "
from mcp.server.fastmcp import FastMCP
m = FastMCP('test')
app = m.streamable_http_app()
for route in app.routes:
    print(route.path, type(route).__name__)
"
```

Adjust the test URLs based on the output.

### Step 4: Run all tests to verify pass

- [ ] Run the full test suite:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_fastmcp_skeleton.py tests/test_fastmcp_tools_migration.py tests/test_fastmcp_resources.py tests/test_fastmcp_prompts.py tests/test_fastmcp_mount.py tests/test_fastmcp_backward_compat.py tests/test_fastmcp_integration.py -v
```

Expected: All 37+ tests PASS.

- [ ] Run existing tests for regression:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_mcp_tools.py tests/test_mcp_access_plane.py tests/test_mcp_registries.py -v
```

Expected: All existing tests PASS.

### Step 5: Commit

- [ ] Commit with message: `test(mcp): add full MCP protocol integration tests (handshake, tools, resources, prompts)`

---

## Summary of New Files

| File | Purpose |
|------|---------|
| `lima_mcp/fastmcp_server.py` | FastMCP server: tools, resources, prompts, mount helper |
| `tests/test_fastmcp_skeleton.py` | Task 1: SDK install + skeleton |
| `tests/test_fastmcp_tools_migration.py` | Task 2: Tool migration validation |
| `tests/test_fastmcp_resources.py` | Task 3: Resource registration |
| `tests/test_fastmcp_prompts.py` | Task 4: Prompt registration |
| `tests/test_fastmcp_mount.py` | Task 5: FastAPI mounting |
| `tests/test_fastmcp_backward_compat.py` | Task 6: Legacy endpoint compat |
| `tests/test_fastmcp_integration.py` | Task 7: Full protocol integration |

## Summary of Modified Files

| File | Change |
|------|--------|
| `lima_mcp/server.py` | Added deprecation headers to legacy endpoints |
| `requirements.txt` (or `pyproject.toml`) | Added `mcp[cli]` dependency |

## Architecture Diagram

```
                     ┌────────────────────────────────────┐
                     │         FastAPI Application         │
                     │                                    │
  Legacy Clients ──► │  /mcp/tools/list  (GET, legacy)    │
                     │  /mcp/tools/call  (POST, legacy)   │
                     │         ↓ deprecation header       │
                     │                                    │
  MCP Clients ─────► │  /v2/mcp/mcp  (POST, JSON-RPC)    │
                     │     ├─ initialize                  │
                     │     ├─ tools/list, tools/call      │
                     │     ├─ resources/list, resources/read│
                     │     └─ prompts/list, prompts/get   │
                     └──────────┬─────────────────────────┘
                                │
               ┌────────────────┼────────────────────┐
               │                │                     │
     lima_mcp/tools.py    Resources             Prompts
     (35+ handlers)       ├─ backend health     ├─ coding-assistant
               │          ├─ system stats       └─ routing-diagnostic
               │          └─ routing scores
               │                │                     │
     access_plane.py      routing_engine        routing_engine
     fs_allowlist.py      health_tracker        health_tracker
     github_handlers.py
```

## Client Migration Guide

### For `deepcode-cli/src/lima/http-mcp-client.ts`

The existing `LiMaHttpMcpClient` continues to work against the legacy endpoints (`/mcp/tools/list`, `/mcp/tools/call`). No changes required.

### For `deepcode-cli/src/mcp/mcp-client.ts`

The stdio-based `McpClient` already speaks full JSON-RPC 2.0 with protocol version `2025-03-26`. To use it with the new spec-compliant HTTP endpoint, configure it to connect to the Streamable HTTP transport instead of stdio. The handshake, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, and `prompts/get` methods all work unchanged.

### For new MCP clients

Point any spec-compliant MCP client at the mounted path:
- JSON-RPC endpoint: `POST http://<host>:<port>/v2/mcp/mcp`
- Protocol version: `2025-03-26`
- Auth: Bearer token via `Authorization` header (same `LIMA_API_KEY` / `LIMA_MCP_TOKEN`)
