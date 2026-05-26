"""LiMa MCP Tools — expose knowledge and memory as tool endpoints.

Tool definitions live in lima_mcp/tool_defs.py (~390 lines).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lima_mcp.tool_defs import TOOL_DEFINITIONS  # noqa: F401, E402
