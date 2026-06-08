"""Compatibility facade for Function Calling tools."""

from lima_fc_tools import execute_tool, get_tools_schema, registered_handlers, run_fc_loop, stats, tool
from lima_fc_tools.http_client import _get

__all__ = [
    "_get",
    "execute_tool",
    "get_tools_schema",
    "registered_handlers",
    "run_fc_loop",
    "stats",
    "tool",
]
