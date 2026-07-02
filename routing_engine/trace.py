"""Trace span helpers for the routing engine."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Generator

from context_pipeline.tracing import get_current_trace, Span

_log = logging.getLogger(__name__)


def _tracing_enabled() -> bool:
    """Read LIMA_TRACING_ENABLED directly to avoid heavy config import at load time."""
    return os.environ.get("LIMA_TRACING_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


@contextlib.contextmanager
def trace_span(name: str, **metadata) -> Generator[Span | None, None, None]:
    """Start/end a span on the current trace. Yields None when tracing disabled."""
    if not _tracing_enabled():
        yield None
        return

    trace = get_current_trace()
    if trace is None:
        yield None
        return

    span = trace.start_span(name, **metadata)
    try:
        yield span
    except Exception as exc:
        span.metadata["error"] = type(exc).__name__
        span.metadata["error_msg"] = str(exc)
        raise
    finally:
        trace.end_span(span)
