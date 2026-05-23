"""MCP-compatible tool server — FastAPI router for LiMa knowledge tools.

Exposes tools as POST /mcp/tools/list and POST /mcp/tools/call
following a simplified MCP-over-HTTP pattern that IDE clients can invoke.
"""

from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Any

from lima_mcp import TOOL_DEFINITIONS
from lima_mcp.tools import handle_tool_call

router = APIRouter(prefix="/mcp")

_MCP_TOKEN = os.environ.get("LIMA_API_KEY", os.environ.get("LIMA_MCP_TOKEN", ""))


async def _verify_mcp_access(authorization: str = Header(default="")) -> None:
    if not _MCP_TOKEN:
        return
    token = authorization.replace("Bearer ", "").strip()
    if token != _MCP_TOKEN:
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
