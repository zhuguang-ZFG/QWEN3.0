"""Full MCP integration tests -- Task 7.

Tests the complete MCP protocol flow against the FastMCP server using
its internal async API (no HTTP transport required):

- JSON-RPC handshake (initialization options / capabilities)
- Tool listing, schema validation, and dispatch
- Resource listing and reading
- Prompt listing and retrieval
- Cross-component consistency
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_mcp():
    """Return the fully-initialised FastMCP instance."""
    from lima_mcp.fastmcp_server import mcp
    return mcp


# ===========================================================================
# 1. JSON-RPC Handshake / Initialization
# ===========================================================================


class TestMCPHandshake:
    """Verify the JSON-RPC handshake and server capabilities."""

    def test_initialization_options(self):
        """Server must produce valid InitializationOptions."""
        mcp = _get_mcp()
        server = mcp._mcp_server
        opts = server.create_initialization_options()

        assert opts.server_name == "LiMa"
        assert opts.server_version  # non-empty string
        assert opts.instructions  # non-empty string

    def test_capabilities_include_tools(self):
        """ServerCapabilities must advertise tools."""
        mcp = _get_mcp()
        opts = mcp._mcp_server.create_initialization_options()
        caps = opts.capabilities

        assert caps.tools is not None, "Server must advertise tools capability"

    def test_capabilities_include_resources(self):
        """ServerCapabilities must advertise resources."""
        mcp = _get_mcp()
        opts = mcp._mcp_server.create_initialization_options()
        caps = opts.capabilities

        assert caps.resources is not None, "Server must advertise resources capability"

    def test_capabilities_include_prompts(self):
        """ServerCapabilities must advertise prompts."""
        mcp = _get_mcp()
        opts = mcp._mcp_server.create_initialization_options()
        caps = opts.capabilities

        assert caps.prompts is not None, "Server must advertise prompts capability"

    def test_server_name_matches(self):
        """Low-level server name must match the FastMCP instance name."""
        mcp = _get_mcp()
        assert mcp._mcp_server.name == mcp.name == "LiMa"

    def test_instructions_present(self):
        """Server instructions must be non-empty (used in initialize response)."""
        mcp = _get_mcp()
        opts = mcp._mcp_server.create_initialization_options()
        assert len(opts.instructions) > 20  # meaningful text, not a stub


# ===========================================================================
# 2. Tool Listing and Schema Validation
# ===========================================================================


class TestMCPToolsIntegration:
    """Integration tests for MCP tool listing and schemas via the async API."""

    async def test_list_tools_returns_32(self):
        """list_tools() must return exactly 32 tools."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        assert len(tools) == 32, f"Expected 32 tools, got {len(tools)}"

    async def test_all_tools_have_names(self):
        """Every tool returned by list_tools() must have a non-empty name."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.name, "Tool has empty name"

    async def test_all_tools_have_descriptions(self):
        """Every tool must have a non-empty description."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"

    async def test_all_tools_have_input_schema(self):
        """Every tool must expose an inputSchema of type 'object'."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.inputSchema is not None, f"Tool {tool.name} has no inputSchema"
            assert tool.inputSchema.get("type") == "object", (
                f"Tool {tool.name} inputSchema type is {tool.inputSchema.get('type')!r}, expected 'object'"
            )

    async def test_health_check_tool_in_list(self):
        """The health_check tool must appear in list_tools() output."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "health_check" in names

    async def test_search_repo_tool_in_list(self):
        """The search_repo tool (migrated from tool_defs) must appear."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "search_repo" in names

    async def test_search_repo_schema_has_query_property(self):
        """search_repo inputSchema must include a 'query' property."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        search_tool = next(t for t in tools if t.name == "search_repo")
        props = search_tool.inputSchema.get("properties", {})
        assert "query" in props, "search_repo must have a 'query' parameter"

    async def test_tool_names_are_unique(self):
        """No two tools may share the same name."""
        mcp = _get_mcp()
        tools = await mcp.list_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), "Duplicate tool names detected"


# ===========================================================================
# 3. Tool Calling (Dispatch)
# ===========================================================================


class TestMCPToolCalling:
    """Integration tests for MCP tool calling via the async API."""

    async def test_call_health_check(self):
        """Calling health_check via call_tool() returns valid JSON with ok=True."""
        mcp = _get_mcp()
        result = await mcp.call_tool("health_check", {})

        # call_tool returns a list of TextContent objects
        assert len(result) >= 1
        text = result[0].text
        data = json.loads(text)
        assert data["ok"] is True
        assert data["server"] == "LiMa"
        assert "version" in data
        assert "timestamp" in data
        assert "protocol" in data

    async def test_call_migrated_tool_dispatches(self):
        """Calling a migrated tool dispatches to handle_tool_call."""
        mcp = _get_mcp()
        with patch("lima_mcp.tools.handle_tool_call") as mock:
            mock.return_value = {"files": ["server.py", "router.py"], "count": 2}
            result = await mcp.call_tool("search_repo", {"query": "server routing"})

            # FastMCP fills in default parameter values from the ArgModel,
            # so max_results=5 is injected automatically.
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][0] == "search_repo"
            passed = call_args[0][1]
            assert passed["query"] == "server routing"

        # Result is a list of TextContent with JSON-encoded return value
        assert len(result) >= 1
        data = json.loads(result[0].text)
        assert data["count"] == 2
        assert "server.py" in data["files"]

    async def test_call_tool_preserves_arguments(self):
        """All arguments passed to call_tool must reach the handler."""
        mcp = _get_mcp()
        with patch("lima_mcp.tools.handle_tool_call") as mock:
            mock.return_value = {"results": []}
            await mcp.call_tool("dev_search_docs", {
                "query": "python asyncio",
                "domains": ["docs.python.org"],
                "max_results": 3,
            })

            call_args = mock.call_args
            assert call_args[0][0] == "dev_search_docs"
            passed = call_args[0][1]
            assert passed["query"] == "python asyncio"
            assert passed["domains"] == ["docs.python.org"]
            assert passed["max_results"] == 3

    async def test_call_unknown_tool_raises_error(self):
        """Calling a non-existent tool raises a ToolError (correct MCP behaviour)."""
        mcp = _get_mcp()
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Unknown tool"):
            await mcp.call_tool("nonexistent", {})

    async def test_call_tool_error_dict_passthrough(self):
        """A registered tool returning an error dict is passed through as JSON."""
        mcp = _get_mcp()
        with patch("lima_mcp.tools.handle_tool_call") as mock:
            mock.return_value = {"error": "rate limited"}
            result = await mcp.call_tool("search_repo", {"query": "test"})

            data = json.loads(result[0].text)
            assert "error" in data
            assert data["error"] == "rate limited"


# ===========================================================================
# 4. Resource Listing and Reading
# ===========================================================================


class TestMCPResourcesIntegration:
    """Integration tests for MCP resource listing and reading."""

    async def test_list_resources_returns_3(self):
        """list_resources() must return exactly 3 resources."""
        mcp = _get_mcp()
        resources = await mcp.list_resources()
        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}"

    async def test_all_resources_have_valid_uris(self):
        """Every resource must have a URI starting with 'resource://lima/'."""
        mcp = _get_mcp()
        resources = await mcp.list_resources()
        for r in resources:
            uri = str(r.uri)
            assert uri.startswith("resource://lima/"), f"Unexpected URI: {uri}"

    async def test_all_resources_have_descriptions(self):
        """Every resource must have a non-empty description."""
        mcp = _get_mcp()
        resources = await mcp.list_resources()
        for r in resources:
            assert r.description, f"Resource {r.uri} has no description"

    async def test_expected_resource_uris(self):
        """The three expected resource URIs must all be present."""
        mcp = _get_mcp()
        resources = await mcp.list_resources()
        uris = {str(r.uri) for r in resources}
        expected = {
            "resource://lima/backends/health",
            "resource://lima/stats",
            "resource://lima/routing/scores",
        }
        assert expected == uris, f"Missing: {expected - uris}, Extra: {uris - expected}"

    async def test_read_backend_health_resource(self):
        """Reading backends/health returns valid JSON with expected keys."""
        mcp = _get_mcp()
        with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock:
            mock.return_value = {
                "backends": {"cloudflare": {"status": "healthy", "latency_ms": 42}},
                "overall": "healthy",
            }
            result = await mcp.read_resource("resource://lima/backends/health")

        assert len(result) >= 1
        data = json.loads(result[0].content)
        assert data["overall"] == "healthy"
        assert "cloudflare" in data["backends"]

    async def test_read_stats_resource(self):
        """Reading stats returns valid JSON."""
        mcp = _get_mcp()
        with patch("lima_mcp.fastmcp_server._fetch_system_stats") as mock:
            mock.return_value = {"uptime_seconds": 7200, "tools_registered": 32}
            result = await mcp.read_resource("resource://lima/stats")

        data = json.loads(result[0].content)
        assert data["uptime_seconds"] == 7200

    async def test_read_routing_scores_resource(self):
        """Reading routing/scores returns valid JSON with a scores key."""
        mcp = _get_mcp()
        with patch("lima_mcp.fastmcp_server._fetch_routing_scores") as mock:
            mock.return_value = {"scores": {"cf_worker": 0.95}, "source": "test"}
            result = await mcp.read_resource("resource://lima/routing/scores")

        data = json.loads(result[0].content)
        assert "scores" in data
        assert data["scores"]["cf_worker"] == 0.95

    async def test_resource_content_has_mime_type(self):
        """ReadResourceContents must include a mime_type."""
        mcp = _get_mcp()
        with patch("lima_mcp.fastmcp_server._fetch_system_stats") as mock:
            mock.return_value = {"note": "test"}
            result = await mcp.read_resource("resource://lima/stats")

        assert result[0].mime_type is not None


# ===========================================================================
# 5. Prompt Listing and Retrieval
# ===========================================================================


class TestMCPPromptsIntegration:
    """Integration tests for MCP prompt listing and retrieval."""

    async def test_list_prompts_returns_2(self):
        """list_prompts() must return exactly 2 prompts."""
        mcp = _get_mcp()
        prompts = await mcp.list_prompts()
        assert len(prompts) == 2, f"Expected 2 prompts, got {len(prompts)}"

    async def test_expected_prompt_names(self):
        """The two expected prompts must be present."""
        mcp = _get_mcp()
        prompts = await mcp.list_prompts()
        names = {p.name for p in prompts}
        assert "coding-assistant" in names
        assert "routing-diagnostic" in names

    async def test_all_prompts_have_descriptions(self):
        """Every prompt must have a non-empty description."""
        mcp = _get_mcp()
        prompts = await mcp.list_prompts()
        for p in prompts:
            assert p.description, f"Prompt {p.name} has no description"

    async def test_coding_assistant_has_arguments(self):
        """coding-assistant prompt must accept 'language' and 'task'."""
        mcp = _get_mcp()
        prompts = await mcp.list_prompts()
        coding = next(p for p in prompts if p.name == "coding-assistant")
        arg_names = {a.name for a in (coding.arguments or [])}
        assert "language" in arg_names
        assert "task" in arg_names

    async def test_routing_diagnostic_has_arguments(self):
        """routing-diagnostic prompt must accept 'backend'."""
        mcp = _get_mcp()
        prompts = await mcp.list_prompts()
        diag = next(p for p in prompts if p.name == "routing-diagnostic")
        arg_names = {a.name for a in (diag.arguments or [])}
        assert "backend" in arg_names

    async def test_get_coding_assistant_prompt(self):
        """get_prompt('coding-assistant') returns messages with expected content."""
        mcp = _get_mcp()
        result = await mcp.get_prompt("coding-assistant", {
            "language": "rust",
            "task": "implement a web server",
        })

        # Result is a GetPromptResult with a messages list
        assert len(result.messages) >= 1
        msg = result.messages[0]
        assert msg.role == "user"
        assert "rust" in msg.content.text.lower()
        assert "web server" in msg.content.text.lower()

    async def test_get_routing_diagnostic_prompt(self):
        """get_prompt('routing-diagnostic') returns analysis messages."""
        mcp = _get_mcp()
        with patch("lima_mcp.fastmcp_server._fetch_backend_statuses") as mock:
            mock.return_value = {
                "backends": {"openai": {"status": "degraded"}},
                "overall": "degraded",
            }
            result = await mcp.get_prompt("routing-diagnostic", {"backend": "all"})

        assert len(result.messages) >= 1
        msg = result.messages[0]
        assert msg.role == "user"
        assert "routing health" in msg.content.text.lower()

    async def test_get_prompt_result_has_description(self):
        """GetPromptResult must carry a description from the prompt docstring."""
        mcp = _get_mcp()
        result = await mcp.get_prompt("coding-assistant", {
            "language": "python",
            "task": "test",
        })
        assert result.description  # non-empty


# ===========================================================================
# 6. Cross-Component Consistency
# ===========================================================================


class TestMCPCrossComponentConsistency:
    """Tests that verify consistency across tools, resources, and prompts."""

    async def test_tool_defs_all_registered(self):
        """Every tool from tool_defs.py must appear in list_tools() output."""
        mcp = _get_mcp()
        from lima_mcp.tool_defs import TOOL_DEFINITIONS

        tools = await mcp.list_tools()
        registered = {t.name for t in tools}
        defined = {td["name"] for td in TOOL_DEFINITIONS}

        assert defined.issubset(registered), (
            f"Missing tools: {defined - registered}"
        )

    async def test_server_has_all_three_capabilities(self):
        """FastMCP server must expose tools, resources, AND prompts."""
        mcp = _get_mcp()

        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        prompts = await mcp.list_prompts()

        assert len(tools) > 0
        assert len(resources) > 0
        assert len(prompts) > 0

    async def test_total_component_counts(self):
        """Sanity check: 32 tools, 3 resources, 2 prompts."""
        mcp = _get_mcp()

        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        prompts = await mcp.list_prompts()

        assert len(tools) == 32, f"Expected 32 tools, got {len(tools)}"
        assert len(resources) == 3, f"Expected 3 resources, got {len(resources)}"
        assert len(prompts) == 2, f"Expected 2 prompts, got {len(prompts)}"

    def test_mount_function_available(self):
        """mount_mcp must be importable and callable; mcp name must be 'LiMa'."""
        from lima_mcp.fastmcp_server import mcp, mount_mcp
        assert callable(mount_mcp)
        assert mcp.name == "LiMa"

    async def test_manager_and_async_api_agree_on_tool_count(self):
        """The synchronous _tool_manager and async list_tools() must agree."""
        mcp = _get_mcp()
        sync_count = len(mcp._tool_manager.list_tools())
        async_tools = await mcp.list_tools()
        assert sync_count == len(async_tools)

    async def test_manager_and_async_api_agree_on_resource_count(self):
        """The synchronous _resource_manager and async list_resources() must agree."""
        mcp = _get_mcp()
        sync_count = len(mcp._resource_manager.list_resources())
        async_resources = await mcp.list_resources()
        assert sync_count == len(async_resources)

    async def test_manager_and_async_api_agree_on_prompt_count(self):
        """The synchronous _prompt_manager and async list_prompts() must agree."""
        mcp = _get_mcp()
        sync_count = len(mcp._prompt_manager.list_prompts())
        async_prompts = await mcp.list_prompts()
        assert sync_count == len(async_prompts)

    async def test_full_protocol_flow(self):
        """End-to-end: init -> list -> call/read/get in a single sequence.

        This is the 'full protocol flow' test that simulates what a real MCP
        client would do after connecting:
        1. Obtain initialization options (handshake)
        2. List tools, resources, and prompts
        3. Call a tool
        4. Read a resource
        5. Get a prompt
        """
        mcp = _get_mcp()

        # Step 1 -- Handshake
        opts = mcp._mcp_server.create_initialization_options()
        assert opts.server_name == "LiMa"
        assert opts.capabilities.tools is not None
        assert opts.capabilities.resources is not None
        assert opts.capabilities.prompts is not None

        # Step 2 -- List
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        prompts = await mcp.list_prompts()

        assert len(tools) == 32
        assert len(resources) == 3
        assert len(prompts) == 2

        # Step 3 -- Call a tool
        health_result = await mcp.call_tool("health_check", {})
        health_data = json.loads(health_result[0].text)
        assert health_data["ok"] is True

        # Step 4 -- Read a resource
        with patch("lima_mcp.fastmcp_server._fetch_system_stats") as mock:
            mock.return_value = {"uptime_seconds": 100}
            resource_result = await mcp.read_resource("resource://lima/stats")
        stats_data = json.loads(resource_result[0].content)
        assert stats_data["uptime_seconds"] == 100

        # Step 5 -- Get a prompt
        prompt_result = await mcp.get_prompt("coding-assistant", {
            "language": "go",
            "task": "build a CLI",
        })
        assert len(prompt_result.messages) >= 1
        assert "go" in prompt_result.messages[0].content.text.lower()
