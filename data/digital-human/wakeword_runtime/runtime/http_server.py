"""唤醒词 runtime HTTP + WebSocket 服务封装。

ponytail: 模块级工厂 ``build_handler_class`` 取代原 ``_build_server`` 内嵌
``TestRuntimeHandler`` 闭包类——仅捕获 ``test_root / event_bridge /
schedule_restart`` 三个依赖，与三个姐妹模块（``frame_codec`` /
``bridge_request_handler`` / ``websocket_session``）的「模块级纯函数」风格对齐。
握手协议抽到模块级 ``accept_websocket_upgrade`` 接缝函数，仅校验 Upgrade +
Sec-WebSocket-Key（不校验 Sec-WebSocket-Version / RFC6455 origin）；
``_handle_websocket`` 收缩为「调 accept + 委托 websocket_session」三行接缝。
升级路径 = 换 wsproto / starlette 框架后握手层一并下沉。
"""

import json
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from ..bridge import WakewordEventBridge
from . import bridge_request_handler
from . import websocket_session
from .frame_codec import compute_accept, receive_message, send_text
from .wakeword_config import build_wakeword_config_message, save_wakeword_config

# 把纯模块 bridge_request_handler 的 save_wakeword_config 链入真实实现
# （保留兼容性：bridge_request_handler.save_wakeword_config 默认为 None，
# 运行时通过 _resolve_save() 走延迟相对导入兜底；这里显式注入可省一次延迟导入）。
bridge_request_handler.save_wakeword_config = save_wakeword_config
# 同样链入 websocket_session 用的两个回调，让它走真实实现而非延迟相对导入。
websocket_session.handle_bridge_request = bridge_request_handler.handle_bridge_request
websocket_session.build_wakeword_config_message = build_wakeword_config_message


def accept_websocket_upgrade(handler: SimpleHTTPRequestHandler) -> tuple[Any, Any] | None:
    """Run the RFC6455 WebSocket handshake on ``handler``.

    Returns ``(reader, writer)`` (i.e. ``handler.connection`` / ``handler.wfile``)
    on success, or ``None`` after sending a BAD_REQUEST response (caller returns).

    ponytail: 接收 duck-typed ``SimpleHTTPRequestHandler``（仅用其
    ``.headers.get`` / ``.send_response`` / ``.send_header`` /
    ``.end_headers`` / ``.send_error`` / ``.connection`` / ``.wfile``
    七个实例 API）；上限 = 仅校验 Upgrade + Sec-WebSocket-Key，
    不校验 Sec-WebSocket-Version / RFC6455 origin；升级路径 = wsproto handshake。
    """
    if handler.headers.get("Upgrade", "").lower() != "websocket":
        handler.send_error(HTTPStatus.BAD_REQUEST, "expected websocket upgrade")
        return None

    websocket_key = handler.headers.get("Sec-WebSocket-Key")
    if not websocket_key:
        handler.send_error(HTTPStatus.BAD_REQUEST, "missing Sec-WebSocket-Key")
        return None

    accept_value = compute_accept(websocket_key)
    handler.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept_value)
    handler.end_headers()
    return handler.connection, handler.wfile


def build_handler_class(
    test_root: Path,
    event_bridge: WakewordEventBridge,
    schedule_restart: Callable[[], None],
) -> type[SimpleHTTPRequestHandler]:
    """Return a SimpleHTTPRequestHandler subclass bound to the given runtime deps.

    Mirrors what the original ``_build_server`` nested ``TestRuntimeHandler``
    closure captured (``test_root`` for static-file serving + wakeword config,
    ``event_bridge`` for WebSocket session, ``schedule_restart`` for restart
    requests). Kept at module scope so the handler class can be constructed /
    inspected without instantiating ``TestRuntimeHttpServer``.
    """

    class TestRuntimeHandler(SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(test_root), **kwargs)

        def handle(self) -> None:
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self) -> None:
            if self.path == "/wakeword-ws":
                self._handle_websocket(event_bridge)
                return

            if self.path == "/health":
                body = json.dumps({"status": "ok"}).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            super().do_GET()

        def log_message(self, format: str, *args) -> None:
            return

        def _handle_websocket(self, bridge: WakewordEventBridge) -> None:
            # 把 RFC6455 握手协议抽到模块级 accept_websocket_upgrade 接缝函数；
            # 此处仅保留「调 accept → None 则 return → 委托 websocket_session」三行。
            upgraded = accept_websocket_upgrade(self)
            if upgraded is None:
                return
            reader, writer = upgraded
            websocket_session.serve_websocket_session(
                reader=reader,
                writer=writer,
                bridge=bridge,
                test_root=test_root,
                schedule_restart=schedule_restart,
                send_text_writer=send_text,
                receive_reader_writer=receive_message,
            )

    return TestRuntimeHandler


class TestRuntimeHttpServer:
    def __init__(self, test_root: Path, host: str = "0.0.0.0", port: int = 8006) -> None:
        self.test_root = test_root
        self.host = host
        self.port = port
        self.event_bridge = WakewordEventBridge()
        self._restart_handler: Callable[[], None] | None = None
        self._restart_lock = threading.Lock()
        self._server = self._build_server()

    @property
    def page_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/index.html"

    @property
    def bridge_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/wakeword-ws"

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self.event_bridge.close()
        self._server.server_close()

    def set_restart_handler(self, handler: Callable[[], None]) -> None:
        self._restart_handler = handler

    def request_runtime_restart(self) -> None:
        with self._restart_lock:
            handler = self._restart_handler

        if handler is None:
            raise RuntimeError("restart handler is not configured")

        threading.Thread(
            target=self._run_restart_handler,
            name="test-runtime-restart",
            daemon=True,
        ).start()

    def _run_restart_handler(self) -> None:
        handler = self._restart_handler
        if handler is None:
            return
        handler()

    def _build_server(self) -> ThreadingHTTPServer:
        handler_cls = build_handler_class(
            self.test_root,
            self.event_bridge,
            self.request_runtime_restart,
        )
        server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        server.daemon_threads = True
        return server
