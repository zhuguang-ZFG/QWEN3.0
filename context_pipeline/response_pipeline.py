"""Response Processor Pipeline — post-response ordered processing.

Based on Google ADK Response Processors pattern:
- quality_check_processor: Detect empty/truncated/garbled responses
- memory_capture_processor: Extract response summary for session memory
- event_recording_processor: Record RESPONSE_RECEIVED/ERROR events
- lesson_extraction_processor: Extract lessons from failures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ResponseContext:
    """Mutable context for response processing."""

    backend: str = ""
    response_text: str = ""
    status_code: int = 200
    latency_ms: int = 0
    error: str = ""

    # Derived by processors
    quality_ok: bool = True
    quality_issues: list[str] = field(default_factory=list)
    summary: str = ""
    lesson: str = ""

    # Pipeline metadata
    processors_applied: list[str] = field(default_factory=list)


ResponseProcessor = Callable[[ResponseContext], ResponseContext]


class ResponsePipeline:
    """Ordered chain of response processors."""

    def __init__(self) -> None:
        self._processors: list[tuple[str, ResponseProcessor]] = []

    def add(self, name: str, processor: ResponseProcessor) -> "ResponsePipeline":
        self._processors.append((name, processor))
        return self

    def process(self, ctx: ResponseContext) -> ResponseContext:
        for name, proc in self._processors:
            ctx = proc(ctx)
            ctx.processors_applied.append(name)
        return ctx
