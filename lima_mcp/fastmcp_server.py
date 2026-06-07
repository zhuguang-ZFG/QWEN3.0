"""FastMCP spec-compliant server for LiMa.

Exposes tools, resources, and prompts via JSON-RPC 2.0 over Streamable HTTP,
using the official `mcp` Python SDK (FastMCP).
"""
from __future__ import annotations

import datetime
import json
import keyword
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools.base import Tool
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase, FuncMetadata
from pydantic import Field, create_model

import lima_mcp.tools as _tools_module
from lima_mcp.tool_defs import TOOL_DEFINITIONS

_log = logging.getLogger(__name__)

# JSON Schema primitive type → Python type mapping
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


# ── FastMCP instance ────────────────────────────────────────────────────────
mcp = FastMCP(
    "LiMa",
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


# ── Data-fetching helpers for resources (graceful degradation) ──────────────

def _fetch_backend_statuses() -> dict:
    """Fetch backend health statuses from the health_tracker module.

    Returns a stub response if the module is unavailable.
    """
    try:
        import health_tracker
        health_map = health_tracker.get_health_map()
        backends = {}
        for name, info in (health_map or {}).items():
            backends[name] = {
                "status": info.get("status", "unknown") if isinstance(info, dict) else str(info),
                "latency_ms": info.get("latency_ms", None) if isinstance(info, dict) else None,
            }
        overall = "healthy" if all(
            b.get("status") in ("healthy", "ok", "up") for b in backends.values()
        ) else "degraded"
        return {"backends": backends, "overall": overall}
    except (ImportError, Exception) as exc:
        _log.debug("Could not fetch backend statuses: %s", exc)
        return {"backends": {}, "overall": "unknown", "note": "health_tracker unavailable"}


def _fetch_system_stats() -> dict:
    """Fetch system statistics (request counts, uptime, etc.).

    Returns a stub response if the tracking module is unavailable.
    """
    try:
        import request_tracking
        stats = {}
        if hasattr(request_tracking, "get_stats"):
            stats = request_tracking.get_stats()
        elif hasattr(request_tracking, "get_metrics"):
            stats = request_tracking.get_metrics()
        return dict(stats) if stats else {"note": "no stats endpoint"}
    except (ImportError, Exception) as exc:
        _log.debug("Could not fetch system stats: %s", exc)
        return {"uptime_seconds": 0, "tools_registered": 0, "note": "request_tracking unavailable"}


def _fetch_routing_scores() -> dict:
    """Fetch current routing/backend scores from the routing subsystem.

    Returns a stub response if the modules are unavailable.
    """
    try:
        import health_tracker
        scores = health_tracker.get_scores()
        return {"scores": dict(scores) if scores else {}, "source": "health_tracker"}
    except (ImportError, Exception) as exc:
        _log.debug("Could not fetch health_tracker scores: %s", type(exc).__name__)
    try:
        import routing_selector
        if hasattr(routing_selector, "route_scorer"):
            scorer = routing_selector.route_scorer
            if hasattr(scorer, "get_scores"):
                return {"scores": dict(scorer.get_scores()), "source": "routing_selector"}
        return {"scores": {}, "source": "routing_selector", "note": "no scorer available"}
    except (ImportError, Exception) as exc:
        _log.debug("Could not fetch routing scores: %s", exc)
        return {"scores": {}, "note": "routing modules unavailable"}


# ── MCP Resources ────────────────────────────────────────────────────────────

@mcp.resource("resource://lima/backends/health")
def get_backend_health() -> str:
    """Return current backend health statuses as JSON.

    Use this resource to monitor the health and availability of LiMa's
    backend AI providers.
    """
    return json.dumps(_fetch_backend_statuses(), indent=2)


@mcp.resource("resource://lima/stats")
def get_stats() -> str:
    """Return system statistics as JSON.

    Provides uptime, request counts, and other operational metrics for
    the LiMa MCP server.
    """
    return json.dumps(_fetch_system_stats(), indent=2)


@mcp.resource("resource://lima/routing/scores")
def get_routing_scores() -> str:
    """Return current routing scores as JSON.

    Exposes the internal scoring data used by LiMa's routing engine to
    select the best backend for each request.
    """
    return json.dumps(_fetch_routing_scores(), indent=2)


# ── MCP Prompts ─────────────────────────────────────────────────────────────

@mcp.prompt(name="coding-assistant")
def coding_assistant_prompt(
    language: str = "python",
    task: str = "general coding",
) -> list:
    """Generate a coding-assistant system prompt for the given language and task.

    Use this prompt to bootstrap an AI coding assistant session tailored to a
    specific programming language and task description.
    """
    return [
        {
            "role": "user",
            "content": (
                f"You are an expert {language} developer assistant. "
                f"Your current task is: {task}.\n\n"
                f"Guidelines:\n"
                f"- Write clean, idiomatic {language} code.\n"
                f"- Follow best practices and PEP/style conventions for {language}.\n"
                f"- Explain your reasoning when making design decisions.\n"
                f"- Include type hints and docstrings where appropriate.\n"
                f"- If the task is ambiguous, ask clarifying questions before coding."
            ),
        }
    ]


@mcp.prompt(name="routing-diagnostic")
def routing_diagnostic_prompt(backend: str = "all") -> list:
    """Generate a routing-diagnostic prompt using live backend health data.

    Fetches current backend statuses via ``_fetch_backend_statuses()`` and
    produces a user message asking the AI to analyse the routing health of
    the specified backend (or all backends when ``backend='all'``).
    """
    health_data = _fetch_backend_statuses()
    health_json = json.dumps(health_data, indent=2)

    scope = (
        f"the '{backend}' backend" if backend != "all" else "all backends"
    )

    return [
        {
            "role": "user",
            "content": (
                f"Analyse the routing health for {scope}.\n\n"
                f"Current backend status snapshot:\n"
                f"```json\n{health_json}\n```\n\n"
                f"Please:\n"
                f"1. Summarise the overall health ({health_data.get('overall', 'unknown')}).\n"
                f"2. Identify any degraded or unhealthy backends.\n"
                f"3. Suggest remediation steps if issues are detected.\n"
                f"4. Highlight backends with high latency (>500 ms)."
            ),
        }
    ]


# ── Dispatcher ───────────────────────────────────────────────────────────────
def _dispatch_tool_call(tool_name: str, arguments: dict) -> dict:
    """Route a FastMCP tool invocation to the legacy handler in tools.py.

    This is the single entry-point used by every dynamically-registered tool
    so that the original implementation in ``lima_mcp.tools.handle_tool_call``
    remains the source of truth for tool behaviour.
    """
    return _tools_module.handle_tool_call(tool_name, arguments)


# ── Dynamic tool registration helpers ────────────────────────────────────────

def _safe_field_name(name: str) -> str:
    """Return a valid Python identifier for *name*, appending ``_`` if needed.

    Python keywords (e.g. ``from``) cannot be used as function parameters or
    pydantic field names directly, so we append an underscore and rely on
    pydantic's ``alias`` mechanism to preserve the original name in the JSON
    schema and in the kwargs dict forwarded to the handler.
    """
    if keyword.iskeyword(name):
        return f"{name}_"
    return name


def _build_arg_model(
    tool_name: str,
    properties: dict,
    required: list[str],
) -> type[ArgModelBase]:
    """Create a pydantic ``ArgModelBase`` subclass from a JSON Schema fragment.

    The resulting model is used by :class:`FuncMetadata` to validate incoming
    arguments and by ``model_json_schema(by_alias=True)`` to produce the MCP
    ``inputSchema``.
    """
    fields: dict = {}
    for pname, pschema in properties.items():
        py_type = _JSON_TYPE_MAP.get(pschema.get("type", "string"), str)
        is_required = pname in required
        has_default = "default" in pschema
        safe_name = _safe_field_name(pname)
        needs_alias = safe_name != pname

        field_kwargs: dict = {}
        if needs_alias:
            field_kwargs["alias"] = pname

        if is_required:
            if has_default:
                # Required parameter with a default value
                default_val = pschema["default"]
                if needs_alias:
                    fields[safe_name] = (py_type, Field(default=default_val, **field_kwargs))
                else:
                    fields[safe_name] = (py_type, default_val)
            else:
                # Required parameter without a default — use Ellipsis (...)
                if needs_alias:
                    fields[safe_name] = (py_type, Field(..., **field_kwargs))
                else:
                    fields[safe_name] = (py_type, ...)
        else:
            if has_default:
                # Optional parameter with a default value
                default_val = pschema["default"]
                if needs_alias:
                    fields[safe_name] = (py_type, Field(default=default_val, **field_kwargs))
                else:
                    fields[safe_name] = (py_type, default_val)
            else:
                # Optional parameter without a default — Optional with None
                if needs_alias:
                    fields[safe_name] = (Optional[py_type], Field(default=None, **field_kwargs))
                else:
                    fields[safe_name] = (Optional[py_type], None)

    model_name = f"{tool_name}_Arguments"
    return create_model(model_name, __base__=ArgModelBase, **fields)


def _make_wrapper(tool_name: str):
    """Return a ``**kwargs`` dispatcher function for the named tool."""

    def wrapper(**kwargs) -> dict:
        return _dispatch_tool_call(tool_name, kwargs)

    wrapper.__name__ = tool_name
    wrapper.__qualname__ = tool_name
    return wrapper


def _register_tools() -> None:
    """Dynamically register every tool from ``tool_defs.py`` onto FastMCP.

    For each entry in ``TOOL_DEFINITIONS`` a pydantic argument model is built
    from the JSON Schema, a thin wrapper function is created, and a
    :class:`Tool` object is injected directly into the tool manager.  This
    gives full control over the ``inputSchema`` while still leveraging
    FastMCP's argument validation at call time.
    """
    for td in TOOL_DEFINITIONS:
        tool_name: str = td["name"]
        tool_desc: str = td["description"]
        tool_params: dict = td.get("parameters", {})
        properties: dict = tool_params.get("properties", {})
        required: list = tool_params.get("required", [])

        arg_model = _build_arg_model(tool_name, properties, required)
        fn_metadata = FuncMetadata(arg_model=arg_model)
        parameters = arg_model.model_json_schema(by_alias=True)

        wrapper = _make_wrapper(tool_name)
        wrapper.__doc__ = tool_desc

        tool = Tool(
            fn=wrapper,
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            fn_metadata=fn_metadata,
            is_async=False,
            context_kwarg=None,
        )

        mcp._tool_manager._tools[tool.name] = tool
        _log.debug("Registered FastMCP tool: %s", tool_name)


# Execute registration at import time so that the ``mcp`` instance is fully
# populated before any test or server code accesses it.
_register_tools()


# ── Mount helper ─────────────────────────────────────────────────────────────

def mount_mcp(app, path: str = "/v2/mcp"):
    """Mount the FastMCP Streamable HTTP app onto a FastAPI application.

    This attaches the MCP JSON-RPC 2.0 endpoint (Streamable HTTP transport)
    as a Starlette sub-application at *path*, keeping it separate from the
    legacy ``/mcp`` router that uses a custom REST-style protocol.

    The MCP endpoint will be available at ``{path}/`` (e.g. ``/v2/mcp/``).
    Clients should POST JSON-RPC messages to that URL.

    Args:
        app: FastAPI (or Starlette) application instance.
        path: URL path prefix for the MCP endpoint (default ``/v2/mcp``).
              The old REST-style MCP router lives at ``/mcp``, so this
              default avoids any routing conflict.
    """
    try:
        # Set the internal Streamable HTTP path to "/" so that the MCP
        # endpoint is served at exactly *path* (not *path*/mcp).
        mcp.settings.streamable_http_path = "/"
        mcp_app = mcp.streamable_http_app()
        app.mount(path, mcp_app)
        _log.info("FastMCP Streamable HTTP mounted at %s", path)
    except Exception as exc:
        _log.warning("Failed to mount FastMCP Streamable HTTP app: %s", exc)
