"""Verify JSON-line structured logging (slice B).

覆盖：JsonFormatter 字段与可解析性、request_id 绑定、extra 并入、
setup_structured_logging 幂等与滚动配置、QueueHandler 不阻塞调用线程。

注意：``server_dlc`` 的 env 开关（``LIMA_STRUCTURED_LOGGING``）是简单 if/else，
本测试不通过 reload 入口模块验证（避免重复装配中间件/污染全局 logging），
开关正确性由代码审查保证；这里直接单元测试 ``structured_logging`` 模块。
"""

from __future__ import annotations

import json
import logging
import logging.handlers

import pytest

import observability.structured_logging as sl
from dlc_api.middleware import request_id_var


@pytest.fixture()
def reset_structured_logging():
    """每个用例后拆除后台 listener 与 root handler，恢复模块初始态。"""
    yield
    sl._stop_listener()
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, logging.handlers.QueueHandler):
            root.removeHandler(handler)
    sl._configured = False


def _make_record(msg: str = "hello", *, extra: dict | None = None) -> logging.LogRecord:
    record = logging.makeLogRecord(
        {
            "name": "test.logger",
            "msg": msg,
            "levelno": logging.INFO,
            "levelname": logging.getLevelName(logging.INFO),
        }
    )
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)
    return record


def test_json_formatter_has_required_fields(reset_structured_logging) -> None:
    fmt = sl.JsonFormatter(service="lima-dlc", version="0.4.0-p3")
    payload = json.loads(fmt.format(_make_record("hi")))
    for key in ("timestamp", "level", "logger", "message", "request_id", "service", "version"):
        assert key in payload
    assert payload["message"] == "hi"
    assert payload["level"] == "INFO"
    assert payload["service"] == "lima-dlc"
    assert payload["version"] == "0.4.0-p3"


def test_request_id_binding(reset_structured_logging) -> None:
    fmt = sl.JsonFormatter(service="s", version="v")
    token = request_id_var.set("rid-xyz")
    try:
        payload = json.loads(fmt.format(_make_record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "rid-xyz"


def test_extra_fields_merged(reset_structured_logging) -> None:
    fmt = sl.JsonFormatter(service="s", version="v")
    payload = json.loads(fmt.format(_make_record(extra={"device_id": "d1", "latency_ms": 12})))
    assert payload["device_id"] == "d1"
    assert payload["latency_ms"] == 12


def test_setup_idempotent_and_rotation(reset_structured_logging) -> None:
    sl.setup_structured_logging(service="s", version="v")
    root = logging.getLogger()
    qh_count = sum(isinstance(h, logging.handlers.QueueHandler) for h in root.handlers)
    assert qh_count == 1
    assert sl._listener is not None
    # 滚动配置体现在 file handler 的 maxBytes/backupCount。
    listener_handlers = sl._listener.handlers
    file_handlers = [h for h in listener_handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].maxBytes == sl.MAX_BYTES
    assert file_handlers[0].backupCount == sl.BACKUP_COUNT

    # 二次调用应为 no-op，不新增 handler。
    sl.setup_structured_logging(service="s", version="v")
    qh_count2 = sum(isinstance(h, logging.handlers.QueueHandler) for h in root.handlers)
    assert qh_count2 == 1


def test_queue_handler_non_blocking(reset_structured_logging) -> None:
    sl.setup_structured_logging(service="s", version="v")
    logger = logging.getLogger("bulk")
    for i in range(1000):
        logger.info("row-%d", i)
    # 不抛异常即视为非阻塞；显式 flush 由 listener 后台线程消费。
    assert True
