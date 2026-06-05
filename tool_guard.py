"""Tool execution guard — doom loop detection + output truncation.

Ported from OpenCode:
- processor.ts:328-349 — doom loop detection (≥3 identical consecutive calls)
- tool.ts:108-125 — tool output truncation with context budget awareness
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ── Doom Loop Detection (processor.ts:328-349) ───────────────────────────────

DOOM_LOOP_THRESHOLD = 3  # consecutive identical calls before triggering
DOOM_LOOP_MAX_WINDOW = 20  # max recent calls to track per session


@dataclass
class DoomLoopGuard:
    """Detects when the LLM gets stuck in a tool-calling loop.

    Tracks the most recent tool calls per session. When the same tool
    is called with the same arguments ≥3 times consecutively, signals
    a doom loop so the caller can inject a corrective system message.
    """

    _history: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=DOOM_LOOP_MAX_WINDOW))

    def record(self, tool_name: str, args: dict[str, Any] | str) -> None:
        """Record a tool call in the session history."""
        args_str = _normalize_args(args)
        self._history.append((tool_name, args_str))

    def is_doom_loop(self, tool_name: str, args: dict[str, Any] | str) -> bool:
        """Check if this call would trigger a doom loop detection."""
        args_str = _normalize_args(args)
        key = (tool_name, args_str)

        # Count consecutive occurrences of this exact (tool, args) pair
        count = 0
        for entry in reversed(self._history):
            if entry == key:
                count += 1
            else:
                break

        return count >= DOOM_LOOP_THRESHOLD

    def inject_correction(self) -> str:
        """Return a system message to inject when doom loop detected."""
        return (
            "You appear to be stuck in a loop calling the same tool with the same arguments. "
            "The tool is not producing different results. Please try a different approach: "
            "re-read the relevant files, check for errors you may be overlooking, or "
            "ask the user for clarification if you are unsure how to proceed."
        )


def _normalize_args(args: dict[str, Any] | str) -> str:
    """Normalize tool arguments for comparison."""
    if isinstance(args, str):
        return args
    try:
        import json
        return json.dumps(args, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(args)


# ── Tool Output Truncation (tool.ts:108-125) ─────────────────────────────────

# Context budget thresholds (characters). Tool outputs exceeding these are truncated.
DEFAULT_MAX_TOOL_OUTPUT = 16_000   # max chars from a single tool result
HARD_MAX_TOOL_OUTPUT = 40_000      # absolute ceiling
TRUNCATION_WARNING = 1_000         # margin below max to truncate cleanly


def truncate_tool_output(
    output: str,
    max_chars: int = DEFAULT_MAX_TOOL_OUTPUT,
) -> tuple[str, dict[str, Any]]:
    """Truncate tool output to fit within context budget.

    Returns (truncated_output, metadata).
    metadata includes:
      - truncated: bool
      - original_length: int
      - truncated_length: int
      - original_sha256: str (hex digest of full output)

    Ported from OpenCode tool.ts Truncate.Service.
    """
    metadata: dict[str, Any] = {
        "truncated": False,
        "original_length": len(output),
        "truncated_length": len(output),
    }

    if len(output) <= max_chars:
        return output, metadata

    # Truncate with a clean boundary
    truncated = output[: max_chars - TRUNCATION_WARNING]
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:16]

    metadata.update({
        "truncated": True,
        "truncated_length": len(truncated),
        "original_sha256": digest,
    })

    truncated += (
        f"\n\n[... output truncated: {len(output)} chars → {len(truncated)} chars] "
        f"[sha256:{digest}]"
    )

    _log.debug(
        "tool output truncated: %d → %d chars (sha256:%s)",
        len(output), len(truncated), digest,
    )

    return truncated, metadata


# ── Tool Call Identity (for hashing/dedup) ───────────────────────────────────

def tool_call_identity(tool_name: str, args: dict[str, Any] | str) -> str:
    """Generate a deterministic identity hash for a tool call.

    Used for deduplication, doom loop detection, and audit trails.
    """
    payload = f"{tool_name}:{_normalize_args(args)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
