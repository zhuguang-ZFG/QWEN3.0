import json
import queue
import socket
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from ..bridge import WakewordEventBridge
from . import bridge_request_handler
from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text
from .wakeword_config import build_wakeword_config_message, save_wakeword_config

# 把纯模块 bridge_request_handler 的 save_wakeword_config 链入真实实现
# （保留兼容性：bridge_request_handler.save_wakeword_config 默认为 None，
# 运行时通过 _resolve_save() 走延迟相对导入兜底；这里显式注入可省一次延迟导入）。
bridge_request_handler.save_wakeword_config = save_wakeword_config


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
        test_root = self.test_root
        event_bridge = self.event_bridge
        schedule_restart = self.request_runtime_restart

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
                if self.headers.get("Upgrade", "").lower() != "websocket":
                    self.send_error(HTTPStatus.BAD_REQUEST, "expected websocket upgrade")
                    return

                websocket_key = self.headers.get("Sec-WebSocket-Key")
                if not websocket_key:
                    self.send_error(HTTPStatus.BAD_REQUEST, "missing Sec-WebSocket-Key")
                    return

                accept_value = compute_accept(websocket_key)

                client_queue = bridge.add_client()
                self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept_value)
                self.end_headers()

                try:
                    self.connection.settimeout(0.2)
                    self._send_websocket_text(bridge.build_ready_message())
                    self._send_websocket_text(self._build_wakeword_config_message(bridge))

                    while bridge.is_running:
                        inbound_message = self._receive_websocket_message()
                        if inbound_message is not None:
                            response_message = self._handle_bridge_request(bridge, inbound_message)
                            if response_message:
                                self._send_websocket_text(response_message)

                        try:
                            message = client_queue.get(timeout=0.2)
                            if message == "__bridge_closed__":
                                break
                            self._send_websocket_text(message)
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

            def _build_wakeword_config_message(self, bridge: WakewordEventBridge) -> str:
                return build_wakeword_config_message(bridge, test_root)

            def _handle_bridge_request(self, bridge: WakewordEventBridge, raw_message: str) -> str | None:
                return bridge_request_handler.handle_bridge_request(bridge, raw_message, test_root, schedule_restart)

            def _save_wakeword_config(self, payload: dict) -> dict:
                return save_wakeword_config(payload, test_root)

            def _receive_websocket_message(self) -> str | None:
                return receive_message(self.connection, self.wfile)

            def _read_exact(self, size: int) -> bytes:
                return read_exact(self.connection, size)

            def _send_websocket_text(self, message: str) -> None:
                send_text(self.wfile, message)

            def _send_websocket_frame(self, opcode: int, payload: bytes) -> None:
                send_frame(self.wfile, opcode, payload)

        server = ThreadingHTTPServer((self.host, self.port), TestRuntimeHandler)
        server.daemon_threads = True
        return server
