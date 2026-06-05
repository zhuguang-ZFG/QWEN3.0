"""opencode_request_headers.py — 解析 OpenCode 客户端发送的会话级 HTTP 头。

复刻 OpenCode session/llm/request.ts 的 headers 构建逻辑 (L170-187)。

OpenCode 客户端发送的关键头部:
- x-session-affinity: sessionID，用于会话亲和路由
- x-opencode-session: sessionID (OpenCode 直连)
- x-opencode-request: requestID (消息 ID)
- x-opencode-client: 客户端标识 (如 "opencode/1.0.0")
- x-parent-session-id: 父会话 (compaction 子会话)
- x-opencode-project: 项目 ID

LiMa 服务端解析这些头部，用于:
1. 会话亲和路由 (同一 session 优先路由到同一后端)
2. 请求追踪和调试
3. 识别 compaction 请求 (有 x-parent-session-id)
4. 客户端版本感知

源码参考:
  - opencode-source/packages/opencode/src/session/llm/request.ts (L170-187)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ── Header 常量 (request.ts:170-187) ────────────────────────────────────────
HEADER_SESSION_AFFINITY = "x-session-affinity"
HEADER_OPENCODE_SESSION = "x-opencode-session"
HEADER_OPENCODE_REQUEST = "x-opencode-request"
HEADER_OPENCODE_CLIENT = "x-opencode-client"
HEADER_PARENT_SESSION = "x-parent-session-id"
HEADER_OPENCODE_PROJECT = "x-opencode-project"

# LiMa 自定义响应头
HEADER_LIMA_SESSION = "x-lima-session-id"
HEADER_LIMA_REQUEST = "x-lima-request-id"
HEADER_LIMA_COMPACTION = "x-lima-compaction-hint"


@dataclass
class OpenCodeRequestContext:
    """解析后的 OpenCode 请求上下文。

    包含从 HTTP 头中提取的会话级信息，用于路由决策和日志追踪。
    """

    session_id: str = ""
    request_id: str = ""
    client_id: str = ""
    parent_session_id: str = ""
    project_id: str = ""
    is_compaction_request: bool = False
    raw_headers: dict[str, str] = field(default_factory=dict)

    @property
    def has_session(self) -> bool:
        return bool(self.session_id)

    @property
    def affinity_key(self) -> str:
        """用于后端亲和路由的 key。优先 session_id，回退 parent_session_id。"""
        return self.session_id or self.parent_session_id or ""


def parse_opencode_headers(headers: dict[str, str] | Any) -> OpenCodeRequestContext:
    """从 HTTP 请求头中解析 OpenCode 会话上下文。

    Args:
        headers: HTTP 请求头字典或 Starlette Headers 对象。
                 支持大小写不敏感查找。

    Returns:
        解析后的 OpenCodeRequestContext。
    """
    # 规范化为小写 key dict (Starlette Headers 已支持)
    if hasattr(headers, "get"):
        get = headers.get
    else:
        normalized = {k.lower(): v for k, v in (headers or {}).items()}
        get = normalized.get

    session_id = (
        _safe_get(get, HEADER_SESSION_AFFINITY)
        or _safe_get(get, HEADER_OPENCODE_SESSION)
        or ""
    )
    request_id = _safe_get(get, HEADER_OPENCODE_REQUEST) or ""
    client_id = _safe_get(get, HEADER_OPENCODE_CLIENT) or ""
    parent_session_id = _safe_get(get, HEADER_PARENT_SESSION) or ""
    project_id = _safe_get(get, HEADER_OPENCODE_PROJECT) or ""

    # compaction 请求有 x-parent-session-id 头
    is_compaction = bool(parent_session_id)

    ctx = OpenCodeRequestContext(
        session_id=session_id,
        request_id=request_id,
        client_id=client_id,
        parent_session_id=parent_session_id,
        project_id=project_id,
        is_compaction_request=is_compaction,
    )

    if session_id:
        _log.debug(
            "parsed opencode headers: session=%s request=%s client=%s compaction=%s",
            session_id[:12], request_id[:12] if request_id else "",
            client_id, is_compaction,
        )

    return ctx


def _safe_get(get_fn, key: str) -> str | None:
    """安全获取 header 值，处理 None 和空字符串。"""
    try:
        val = get_fn(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except (TypeError, KeyError, AttributeError):
        pass
    # 尝试原始大小写 (某些 HTTP 框架保持原始大小写)
    try:
        # 把 x-foo-bar 转成 X-Foo-Bar
        title_key = "-".join(p.capitalize() for p in key.split("-"))
        val = get_fn(title_key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except (TypeError, KeyError, AttributeError):
        pass
    return None


def build_response_headers(ctx: OpenCodeRequestContext) -> dict[str, str]:
    """构建 LiMa 响应头，回传会话信息给 OpenCode 客户端。

    Args:
        ctx: 解析后的请求上下文。

    Returns:
        响应头字典。
    """
    resp: dict[str, str] = {}

    if ctx.session_id:
        resp[HEADER_LIMA_SESSION] = ctx.session_id
    if ctx.request_id:
        resp[HEADER_LIMA_REQUEST] = ctx.request_id

    return resp


def extract_backend_from_session(session_id: str, available_backends: list[str]) -> str | None:
    """基于 session affinity 选择后端。

    简单哈希策略: 同一 session_id 始终路由到同一后端，
    确保会话内的上下文连贯性。

    Args:
        session_id: 会话 ID。
        available_backends: 可用后端列表。

    Returns:
        选中的后端名称，或 None (如果无法确定)。
    """
    if not session_id or not available_backends:
        return None

    # 用 session_id 的哈希值选择后端
    idx = hash(session_id) % len(available_backends)
    return available_backends[idx]


def is_opencode_client(headers: dict[str, str] | Any) -> bool:
    """检测请求是否来自 OpenCode 客户端。

    通过 x-opencode-client 或 User-Agent 头检测。

    Args:
        headers: HTTP 请求头。

    Returns:
        True 表示来自 OpenCode 客户端。
    """
    if hasattr(headers, "get"):
        get = headers.get
    else:
        normalized = {k.lower(): v for k, v in (headers or {}).items()}
        get = normalized.get

    # 直接标记
    client = _safe_get(get, HEADER_OPENCODE_CLIENT)
    if client:
        return True

    # User-Agent 检测
    ua = _safe_get(get, "user-agent") or ""
    return "opencode" in ua.lower()
