"""Structured (JSON-line) logging for the DLC server.

启用方式：环境变量 ``LIMA_STRUCTURED_LOGGING=1`` 时，``server_dlc`` 在启动期
调用 :func:`setup_structured_logging` 替换默认 ``logging.basicConfig``。默认
（未设置）保持原有文本日志不变，做到零侵入、可一键回退。

设计要点：
- 单行 JSON（``JsonFormatter``），便于 ELK/Loki/CloudWatch 采集。
- 绑定 ``request_id``（取自 ``dlc_api.middleware.request_id_var``），让一次
  请求链路的所有日志可关联。
- ``QueueHandler`` + ``QueueListener``：日志 I/O 在后台线程完成，调用线程不阻塞。
- ``RotatingFileHandler``：写入 ``logs/dlc.jsonl``，按 50MB 滚动，保留 5 份。
- 同时输出到 ``stderr``，保证 ``docker logs`` 可见。
"""

from __future__ import annotations

import atexit
import datetime
import json
import logging
import logging.handlers
import queue
import sys
from pathlib import Path
from typing import Any

from dlc_api.middleware import request_id_var

LOG_FILE = "logs/dlc.jsonl"
MAX_BYTES = 50 * 1024 * 1024
BACKUP_COUNT = 5

# LogRecord 的标准字段集合，用于识别调用方通过 ``extra=`` 注入的自定义字段。
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}

_listener: logging.handlers.QueueListener | None = None
_configured = False


class JsonFormatter(logging.Formatter):
    """Render each :class:`logging.LogRecord` as a single JSON object line.

    固定字段：``timestamp``(ISO8601 UTC)、``level``、``logger``、``message``、
    ``request_id``、``service``、``version``；异常栈走 ``exc`` 字段；调用方
    通过 ``logger.info("...", extra={"foo": 1})`` 注入的字段原样并入顶层。
    """

    def __init__(self, *, service: str = "", version: str = "") -> None:
        super().__init__()
        self._service = service
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("") or getattr(record, "request_id", ""),
            "service": self._service,
            "version": self._version,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _stop_listener() -> None:
    """atexit hook：优雅停止后台 listener，刷新队列中剩余日志。"""
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def setup_structured_logging(*, service: str, version: str) -> None:
    """Configure the root logger for JSON-line structured output.

    幂等：重复调用不会重复挂 handler / 启动线程。``QueueListener`` 的后台线程
    由 ``atexit`` 注册的 :func:`_stop_listener` 在进程正常退出时停止（标准库
    ``QueueListener`` 线程非 daemon，依赖显式 stop 做干净关闭）。
    """
    global _listener, _configured
    if _configured:
        return

    Path("logs").mkdir(exist_ok=True)
    formatter = JsonFormatter(service=service, version=version)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(queue_handler)

    _listener = logging.handlers.QueueListener(log_queue, file_handler, stream_handler, respect_handler_level=True)
    _listener.start()
    atexit.register(_stop_listener)
    _configured = True
