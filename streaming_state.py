"""Stream state tracking for mid-stream failover and recovery.

Accumulates text chunks, metadata, and token counts during an SSE stream.
When a backend fails mid-stream, the StreamState object contains everything
needed to construct a continuation prompt for a backup backend.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class StreamState:
    """Tracks the accumulated state of an in-progress SSE stream.

    Attributes:
        backend: The backend currently (or most recently) serving the stream.
        accumulated_text: All text content received so far (post-cleaning).
        raw_chunks: List of raw SSE chunk strings received.
        chunk_count: Total number of chunks received.
        received_finish: Whether a finish_reason was received.
        usage: Accumulated usage/token metadata from __LIMA_META__ lines.
        started_at: Timestamp when streaming began.
        failed_at: Timestamp when the stream failed (None if still active).
        failure_reason: Description of the failure, if any.
        failover_count: Number of times failover has been attempted.
        backends_tried: Ordered list of backends that were attempted.
    """

    backend: str = ""
    accumulated_text: str = ""
    raw_chunks: list[str] = field(default_factory=list)
    chunk_count: int = 0
    received_finish: bool = False
    usage: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    failed_at: float | None = None
    failure_reason: str = ""
    failover_count: int = 0
    backends_tried: list[str] = field(default_factory=list)

    def record_chunk(self, chunk: str) -> None:
        """Record a single chunk received from the backend stream.

        Args:
            chunk: The raw text content of the chunk (SSE-normalized).
        """
        self.raw_chunks.append(chunk)
        self.chunk_count += 1

    def record_text(self, text: str) -> None:
        """Accumulate cleaned text content.

        Args:
            text: Cleaned text extracted from the chunk.
        """
        self.accumulated_text += text

    def record_meta(self, meta: dict) -> None:
        """Record metadata from a __LIMA_META__ line.

        Args:
            meta: Parsed metadata dict (e.g., {"usage": {...}} or
                  {"reasoning_content": "..."}).
        """
        if "usage" in meta:
            self.usage.update(meta["usage"])

    def mark_failed(self, reason: str) -> None:
        """Mark the current stream as failed.

        Args:
            reason: Human-readable failure description.
        """
        self.failed_at = time.time()
        self.failure_reason = reason

    def mark_failover(self, new_backend: str) -> None:
        """Record a failover transition to a new backend.

        Args:
            new_backend: The backup backend being switched to.
        """
        self.failover_count += 1
        self.backends_tried.append(new_backend)
        self.backend = new_backend
        self.failure_reason = ""
        self.failed_at = None

    @property
    def elapsed_sec(self) -> float:
        """Seconds since streaming began."""
        return time.time() - self.started_at

    @property
    def is_complete(self) -> bool:
        """True if the stream finished normally (received finish_reason)."""
        return self.received_finish

    @property
    def has_content(self) -> bool:
        """True if any text content was accumulated."""
        return bool(self.accumulated_text.strip())

    @property
    def partial_length(self) -> int:
        """Character count of accumulated partial text."""
        return len(self.accumulated_text)

    def snapshot(self) -> dict:
        """Return a serializable snapshot of the current state.

        Useful for logging and metrics.
        """
        return {
            "backend": self.backend,
            "chunk_count": self.chunk_count,
            "text_length": self.partial_length,
            "received_finish": self.received_finish,
            "failover_count": self.failover_count,
            "backends_tried": list(self.backends_tried),
            "elapsed_sec": round(self.elapsed_sec, 2),
            "failure_reason": self.failure_reason,
            "usage": dict(self.usage),
        }
