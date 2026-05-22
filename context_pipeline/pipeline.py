"""Ordered processor chain for request context transformation.

Each processor is a function: (RequestContext) -> RequestContext
Processors run in sequence, each building on previous outputs.
"""

from __future__ import annotations

from typing import Callable

from . import RequestContext

Processor = Callable[[RequestContext], RequestContext]


class Pipeline:
    """Ordered chain of context processors."""

    def __init__(self) -> None:
        self._processors: list[tuple[str, Processor]] = []

    def add(self, name: str, processor: Processor) -> "Pipeline":
        self._processors.append((name, processor))
        return self

    def process(self, ctx: RequestContext) -> RequestContext:
        for name, proc in self._processors:
            ctx = proc(ctx)
            ctx.processors_applied.append(name)
        return ctx

    @property
    def stages(self) -> list[str]:
        return [name for name, _ in self._processors]
