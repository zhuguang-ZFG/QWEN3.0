"""MCP-compatible tool server — FastAPI router for LiMa knowledge tools.

Exposes tools as POST /mcp/tools/list and POST /mcp/tools/call
following a simplified MCP-over-HTTP pattern that IDE clients can invoke.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
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
async def list_tools():
    return {"tools": TOOL_DEFINITIONS}


@router.post("/tools/call", dependencies=[Depends(_verify_mcp_access)])
async def call_tool(req: ToolCallRequest):
    result = handle_tool_call(req.name, req.arguments)
    return {"result": result}
