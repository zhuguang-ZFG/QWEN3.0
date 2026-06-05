"""Agent step checkpointing — snapshot before/after each agent step.

Ported from OpenCode processor.ts:382-436.
Tracks per-step token usage, tool calls, and context injection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepSnapshot:
    """A snapshot of agent state at a step boundary."""

    step: int
    timestamp: float = field(default_factory=time.time)
    token_count_before: int = 0
    token_count_after: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[str] = field(default_factory=list)
    context_injected: bool = False
    needs_compaction: bool = False

    @property
    def tokens_consumed(self) -> int:
        return self.token_count_after - self.token_count_before

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)


@dataclass
class StepCheckpointer:
    """Tracks agent steps with before/after snapshots.

    Usage:
        cp = StepCheckpointer()
        cp.start_step(0, tokens_before=1500)
        # ... agent runs, makes tool calls ...
        cp.end_step(tokens_after=3200, tool_calls=[...])
        # cp.snapshots now has the step record
    """

    snapshots: list[StepSnapshot] = field(default_factory=list)
    _current: StepSnapshot | None = None
    _max_snapshots: int = 50

    def start_step(self, step: int, token_count: int = 0) -> StepSnapshot:
        """Begin tracking a new agent step."""
        self._current = StepSnapshot(
            step=step,
            token_count_before=token_count,
        )
        return self._current

    def end_step(
        self,
        token_count: int = 0,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_results: list[str] | None = None,
        context_injected: bool = False,
    ) -> StepSnapshot:
        """Complete the current step."""
        if self._current is None:
            self._current = StepSnapshot(step=0)

        self._current.token_count_after = token_count
        self._current.tool_calls = tool_calls or []
        self._current.tool_results = tool_results or []
        self._current.context_injected = context_injected

        self.snapshots.append(self._current)
        if len(self.snapshots) > self._max_snapshots:
            self.snapshots = self.snapshots[-self._max_snapshots:]

        result = self._current
        self._current = None
        return result

    def total_tokens(self) -> int:
        return sum(s.tokens_consumed for s in self.snapshots)

    def total_tool_calls(self) -> int:
        return sum(s.tool_call_count for s in self.snapshots)

    def is_over_limit(self, max_tokens: int = 128_000) -> bool:
        return self.total_tokens() > max_tokens

    def summary(self) -> dict[str, Any]:
        return {
            "steps": len(self.snapshots),
            "total_tokens": self.total_tokens(),
            "total_tool_calls": self.total_tool_calls(),
            "needs_compaction": any(s.needs_compaction for s in self.snapshots),
        }
