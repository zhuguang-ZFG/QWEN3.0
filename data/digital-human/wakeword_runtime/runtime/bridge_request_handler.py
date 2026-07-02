"""唤醒词 runtime 桥接请求处理纯函数。

ponytail: 不依赖 self/socket/connection/Handler instance，只接受 bridge/raw
_message/test_root/schedule_restart 四个参数，便于单测；上限是仅处理三种
已知 message_type（set_wakeword_config / restart_wakeword_service / 其他
归 unknown），未做协议版本协商与 schema 校验。升级路径：若需 schema 校验
（pydantic）或协议版本协商，换用 wsproto + 结构化 schema 包。

依赖：save_wakeword_config 来自 wakeword_config 模块（已是纯函数）。
为了让 importlib 无父包场景下也能加载本模块做单测，模块顶部**不**做相对导入；
_run_save() 在每次 set_wakeword_config 调用时读本模块属性 save_wakeword_config
（生产环境由 http_server 在 import 后 setattr 链入；测试用 monkeypatch 注入
fake）。如未配置，回退到 `from .wakeword_config import save_wakeword_config`
的延迟相对导入（仅在真实 runtime-package 上下文可达）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 已支持的 message_type 常量，便于阅读与未来扩展。
_TYPE_SET_WAKEWORD = "set_wakeword_config"
_TYPE_RESTART = "restart_wakeword_service"

# 由 http_server 在 import 后链入或由测试 monkeypatch 注入（默认 None，运行时
# 通过 _resolve_save() 解析）。ponytail: 顶层属性而非 from-import，避开 importlib
# 无父包相对导入失败；上限是测试必须改本属性才生效（生产代码也走同一通路）。
save_wakeword_config: Any = None


def _resolve_save():
    """若 save_wakeword_config 已被注入则直接用；否则延迟相对导入兜底。"""
    if save_wakeword_config is not None:
        return save_wakeword_config
    from .wakeword_config import save_wakeword_config as _s  # noqa: F811

    return _s


def handle_bridge_request(
    bridge: Any,
    raw_message: str,
    test_root: Path,
    schedule_restart: Callable[[], None],
) -> str | None:
    """解析并处理一条来自客户端的 WebSocket 文本消息。

    返回：
    - 成功/失败结果时：一个由 `bridge.build_message` 序列化的 JSON 字符串，
      该字符串由调用方通过 WebSocket 文本帧回送客户端。
    - JSON 解析失败或未知 subtype 不属于Суд结果时：``None``（调用方静默忽略）。

    遵循 AGENTS.md 硬规则 #1（禁止静默降级）：对 set_wakeword_config 的保存
    失败，捕获 Exception 后显式回送 success=False 携带错误描述，不发 except
    pass；日志层不重复打 logger.warning（结果已包含 error 字段供前端解读）。
    """
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        return None

    message_type = str(message.get("type", "")).strip()
    request_id = message.get("requestId")
    payload = message.get("payload") or {}
    result_type = f"{message_type}_result" if message_type else "bridge_request_result"

    if message_type == _TYPE_SET_WAKEWORD:
        return _handle_set_wakeword_config(bridge, payload, request_id, test_root)

    if message_type == _TYPE_RESTART:
        return _handle_restart(bridge, request_id, schedule_restart)

    return bridge.build_message(
        result_type,
        {},
        request_id=request_id,
        success=False,
        error=f"unsupported message type: {message_type}",
    )


def _handle_set_wakeword_config(
    bridge: Any,
    payload: dict,
    request_id: object,
    test_root: Path,
) -> str:
    """处理 set_wakeword_config 请求：保存 + 发布事件回送结果。"""
    try:
        result_payload = _resolve_save()(payload, test_root)
        bridge.publish("wakeword_config", result_payload)
        return bridge.build_message(
            "set_wakeword_config_result",
            result_payload,
            request_id=request_id,
        )
    except Exception as exc:
        return bridge.build_message(
            "set_wakeword_config_result",
            {},
            request_id=request_id,
            success=False,
            error=f"保存唤醒词配置失败: {exc}",
        )


def _handle_restart(
    bridge: Any,
    request_id: object,
    schedule_restart: Callable[[], None],
) -> str:
    """处理 restart_wakeword_service 请求：触发 restart 并回送 restarting 状态。"""
    schedule_restart()
    return bridge.build_message(
        "restart_wakeword_service_result",
        {"restarting": True},
        request_id=request_id,
    )
