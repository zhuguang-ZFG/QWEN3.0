#!/usr/bin/env python3
"""LiMa 运维工具函数 —— 从 lima_ops_mcp.py 提取。

每个工具函数接受 run_ssh、servers、logger 作为参数注入，
而非直接从父模块导入。实际实现已拆分到 lima_mcp_stdio/ops/ 子模块。
"""

from __future__ import annotations

from lima_mcp_stdio.ops.device_connections import tool_device_connections
from lima_mcp_stdio.ops.health_check import tool_health_check
from lima_mcp_stdio.ops.restart_service import tool_restart_service
from lima_mcp_stdio.ops.server_status import tool_server_status
from lima_mcp_stdio.ops.tail_log import tool_tail_log

__all__ = [
    "tool_device_connections",
    "tool_health_check",
    "tool_restart_service",
    "tool_server_status",
    "tool_tail_log",
]
