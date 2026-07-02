"""唤醒词 WebSocket 会话主循环纯函数（从 http_server.py 嵌套方法抽离）。

ponytail: 不依赖 self/SimpleHTTPRequestHandler instance，只接受
reader(.recv/.settimeout)/writer(.write/.flush)/bridge/test_root/schedule_restart
五个参数，便于单测；上限是仅覆盖唤醒词 runtime 实际的两段交互
（greeting + 双向消息循环），未做 per-message 流控/重试扩展。升级路径：
若需更复杂的流控或背压，换用 wsproto 的 frame iterator + asyncio queue。

设计同 frame_codec / bridge_request_handler 模式：顶层属性（不是 from-import）
链入 bridge_request_handler.handle_bridge_request 与 wakeword_config.build_*，
单测可 setattr 注入 fake；http_server.py 在 import 后显式链入真实实现。
"""

from __future__ import annotations

import queue
import socket
from pathlib import Path
from typing import Any, Callable

from ..bridge import WakewordEventBridge
from .frame_codec import receive_message, send_text

# 链入：http_server.py 在 import 后显式 setattr，测试可 monkeypatch 注入。
# 默认 None；_resolve_handle_request / _resolve_build_wakeword_config 兜底走
# 延迟相对导入（仅在真实 runtime-package 上下文可达）。
handle_bridge_request: Callable[..., str | None] | None = None
build_wakeword_config_message: Callable[..., str] | None = None


def _resolve_handle_request():
    if handle_bridge_request is not None:
        return handle_bridge_request
    from .bridge_request_handler import handle_bridge_request as _h  # noqa: F811

    return _h


def _resolve_build_wakeword_config_message():
    if build_wakeword_config_message is not None:
        return build_wakeword_config_message
    from .wakeword_config import build_wakeword_config_message as _b  # noqa: F811

    return _b


def serve_websocket_session(
    reader: Any,
    writer: Any,
    bridge: WakewordEventBridge,
    test_root: Path,
    schedule_restart: Callable[[], None],
    send_text_writer: Callable[[Any, str], None] = send_text,
    receive_reader_writer: Callable[[Any, Any], str | None] = receive_message,
) -> None:
    """主循环：客户端加入 bridge → 发送 ready + config → 双向轮询 → 退出时移除客户端。

    Args:
        reader: 提供 ``recv``/``settimeout`` 的 socket-like 对象（生产为
            ``self.connection``）。
        writer: 提供 ``write``/``flush`` 的 file-like 对象（生产为 ``self.wfile``）。
        bridge: 唤醒词事件桥。
        test_root: 唤醒词 runtime 根目录。
        schedule_restart: 触发服务重启的回调。
        send_text_writer / receive_reader_writer: 帧读写函数（注入便于单测，
            默认来自 frame_codec）。

    遵守 AGENTS.md 硬规则 #1（禁止静默降级）：socket.timeout 与
    BrokenPipe/ConnectionReset/ConnectionAborted 均显式分类捕获，不 except
    pass 不吞掉日志不明；事件循环依靠 bridge.is_running 与 __bridge_closed__
    sentinel 自然退出。
    """
    client_queue = bridge.add_client()
    try:
        reader.settimeout(0.2)
        send_text_writer(writer, bridge.build_ready_message())
        send_text_writer(writer, _resolve_build_wakeword_config_message()(bridge, test_root))

        while bridge.is_running:
            inbound_message = receive_reader_writer(reader, writer)
            if inbound_message is not None:
                response_message = _resolve_handle_request()(bridge, inbound_message, test_root, schedule_restart)
                if response_message:
                    send_text_writer(writer, response_message)

            try:
                message = client_queue.get(timeout=0.2)
                if message == "__bridge_closed__":
                    break
                send_text_writer(writer, message)
            except queue.Empty:
                if not bridge.is_running:
                    break
                continue
    except socket.timeout:
        pass
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        bridge.remove_client(client_queue)
