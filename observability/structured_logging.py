"""Structured JSON logging for LiMa — OpenTelemetry-compatible log format.

Enabled via LIMA_STRUCTURED_LOGGING=1.
Outputs JSON lines with trace_id, span_id, and service context for
correlation with OTEL Collector / Loki.
"""

from __future__ import annotations

import json
import logging
import os
import sys

_ENABLED = os.environ.get("LIMA_STRUCTURED_LOGGING", "0").strip().lower() in {
    "1", "true", "yes",
}
_SERVICE_NAME = os.environ.get("LIMA_SERVICE_NAME", "lima-router")


class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines with OTEL-compatible fields."""

    def format(self, record: logging.LogRecord) -> str:
        from context_pipeline.tracing import get_current_trace

        trace = get_current_trace()
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
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


def setup_structured_logging() -> None:
    """Install JSON log formatter on the root logger (called from server lifespan)."""
    if not _ENABLED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)
    _log = logging.getLogger(__name__)
    _log.info("Structured JSON logging enabled for service=%s", _SERVICE_NAME)
