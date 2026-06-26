"""Request Tracing — OpenAI Agents-inspired full lifecycle tracing.

Provides request-level trace IDs and span tracking for observability:
- Each request gets a unique trace_id
- Each processing stage creates a span with timing
- Spans can be nested (parent-child)
- Export to structured format for analysis
"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Span:
    """A single timed span within a trace."""

    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        if self.end_time == 0:
            return int((time.time() - self.start_time) * 1000)
        return int((self.end_time - self.start_time) * 1000)

    @property
    def is_complete(self) -> bool:
        return self.end_time > 0


class RequestTrace:
    """Full trace for a single request lifecycle."""

    def __init__(self) -> None:
        self.trace_id: str = uuid.uuid4().hex[:12]
        self.spans: list[Span] = []
        self.start_time: float = time.time()
        self._active_span: Span | None = None

    def start_span(self, name: str, **metadata) -> Span:
        """Start a new span."""
        parent_id = self._active_span.span_id if self._active_span else ""
        span = Span(
            name=name,
            trace_id=self.trace_id,
            parent_id=parent_id,
            start_time=time.time(),
            metadata=metadata,
        )
        self.spans.append(span)
        self._active_span = span
        return span

    def end_span(self, span: Span | None = None) -> None:
        """End a span (defaults to active span)."""
        target = span or self._active_span
        if target:
            target.end_time = time.time()
        if target == self._active_span:
            parent = next((s for s in self.spans if s.span_id == target.parent_id), None) if target else None
            self._active_span = parent

    @property
    def total_duration_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)

    def finish(self) -> dict:
        """End all active spans and export the trace."""
        while self._active_span is not None:
            self.end_span()
        return self.export()

    def export(self) -> dict:
        """Export trace as structured dict for analysis."""
        return {
            "trace_id": self.trace_id,
            "total_ms": self.total_duration_ms,
            "span_count": len(self.spans),
            "spans": [
                {
                    "name": s.name,
                    "span_id": s.span_id,
                    "parent_id": s.parent_id,
                    "duration_ms": s.duration_ms,
                    "metadata": s.metadata,
                }
                for s in self.spans
            ],
        }


# Context-var scoped trace per request
import contextvars

_current_trace: contextvars.ContextVar[RequestTrace | None] = contextvars.ContextVar("current_trace", default=None)


def new_trace() -> RequestTrace:
    """Create a new trace for the current request."""
    trace = RequestTrace()
    _current_trace.set(trace)
    return trace


def get_current_trace() -> RequestTrace | None:
    return _current_trace.get(None)


def reset_current_trace() -> None:
    """Reset the current trace context var (test isolation only)."""
    _current_trace.set(None)
