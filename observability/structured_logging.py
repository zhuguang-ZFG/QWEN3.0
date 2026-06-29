"""Structured JSON logging for LiMa — OpenTelemetry-compatible log format.

Enabled by default; disable with LIMA_STRUCTURED_LOGGING=0.
Outputs JSON lines with trace_id, span_id, and service context for
correlation with OTEL Collector / Loki.

AUDIT-5-O9：默认启用按大小滚动的文件日志（RotatingFileHandler），防止错误循环冲爆磁盘。
可通过 LIMA_LOG_FILE_PATH 关闭（空字符串），通过 LIMA_LOG_FILE_MAX_MB / LIMA_LOG_FILE_BACKUPS 调整容量。
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from config import settings

_ENABLED = settings.OBSERVABILITY.structured_logging
_SERVICE_NAME = settings.OBSERVABILITY.service_name
_LOG_CFG = settings.OBSERVABILITY


class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines with OTEL-compatible fields."""

    def format(self, record: logging.LogRecord) -> str:
        from context_pipeline.tracing import get_current_trace

        trace = get_current_trace()
        dt = datetime.datetime.utcfromtimestamp(record.created)
        payload = {
            "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": _SERVICE_NAME,
            "module": f"{record.filename}:{record.lineno}",
        }
        if trace:
            payload["trace_id"] = trace.trace_id
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])

        return json.dumps(payload, ensure_ascii=False, default=str)


def _file_formatter() -> logging.Formatter:
    return JsonFormatter() if _ENABLED else logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


def _setup_file_logging() -> None:
    """Install a size-limited RotatingFileHandler on the root logger."""
    path = _LOG_CFG.log_file_path
    if not path:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=_LOG_CFG.log_file_max_bytes,
        backupCount=_LOG_CFG.log_file_backup_count,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(_file_formatter())
    logging.root.addHandler(handler)


def setup_structured_logging() -> None:
    """Install JSON log formatter on the root logger (called from server lifespan)."""
    if not _ENABLED:
        # AUDIT-5-O9：即使结构化日志关闭，也按配置安装滚动文件日志。
        _setup_file_logging()
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)
    _setup_file_logging()
    _log = logging.getLogger(__name__)
    _log.info("Structured JSON logging enabled for service=%s", _SERVICE_NAME)
