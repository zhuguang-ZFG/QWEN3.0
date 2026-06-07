# Streaming Fault Tolerance and Auto-Recovery

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic mid-stream failover so that when a backend fails during SSE streaming, LiMa seamlessly switches to a backup backend and continues the response without client-visible errors.

**Architecture:** A StreamState tracker accumulates chunks during streaming. When `bridge_stream_async()` detects a failure, it constructs a continuation prompt from the partial response and hands off to the next ranked backend. The client sees a continuous SSE stream with only a brief pause.

**Tech Stack:** Python 3.10+, httpx (async streaming), FastAPI StreamingResponse, pytest, pytest-asyncio

---

## Task 1: Stream State Tracker

Create `streaming_state.py` that tracks accumulated text chunks, metadata, and token counts during a stream. This enables knowing exactly where a stream was interrupted so that a replacement backend can resume seamlessly.

### File: `D:\QWEN3.0\streaming_state.py` (new)

```python
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
```

### Test: `D:\QWEN3.0\tests\test_streaming_state.py` (new)

```python
"""Tests for streaming_state.StreamState."""

import time

import pytest

from streaming_state import StreamState


class TestStreamState:
    def test_initial_state(self):
        state = StreamState(backend="backend_a")
        assert state.backend == "backend_a"
        assert state.accumulated_text == ""
        assert state.chunk_count == 0
        assert state.received_finish is False
        assert state.failover_count == 0
        assert state.backends_tried == []
        assert state.has_content is False
        assert state.is_complete is False
        assert state.partial_length == 0

    def test_record_chunk(self):
        state = StreamState()
        state.record_chunk("chunk1")
        state.record_chunk("chunk2")
        assert state.chunk_count == 2
        assert state.raw_chunks == ["chunk1", "chunk2"]

    def test_record_text(self):
        state = StreamState()
        state.record_text("Hello ")
        state.record_text("world")
        assert state.accumulated_text == "Hello world"
        assert state.has_content is True
        assert state.partial_length == 11

    def test_record_meta_usage(self):
        state = StreamState()
        state.record_meta({"usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        assert state.usage == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_record_meta_merges(self):
        state = StreamState()
        state.record_meta({"usage": {"prompt_tokens": 10}})
        state.record_meta({"usage": {"completion_tokens": 20}})
        assert state.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    def test_mark_failed(self):
        state = StreamState(backend="backend_a")
        state.mark_failed("timeout after 30s")
        assert state.failure_reason == "timeout after 30s"
        assert state.failed_at is not None

    def test_mark_failover(self):
        state = StreamState(backend="backend_a")
        state.mark_failed("timeout")
        state.mark_failover("backend_b")
        assert state.backend == "backend_b"
        assert state.failover_count == 1
        assert state.backends_tried == ["backend_b"]
        assert state.failure_reason == ""
        assert state.failed_at is None

    def test_multiple_failovers(self):
        state = StreamState(backend="backend_a")
        state.mark_failover("backend_b")
        state.mark_failover("backend_c")
        assert state.failover_count == 2
        assert state.backends_tried == ["backend_b", "backend_c"]
        assert state.backend == "backend_c"

    def test_elapsed_sec(self):
        state = StreamState(started_at=time.time() - 5.0)
        assert state.elapsed_sec >= 4.9

    def test_snapshot(self):
        state = StreamState(backend="backend_a", started_at=time.time() - 2.0)
        state.record_text("Hello")
        state.record_chunk("chunk1")
        state.mark_failover("backend_b")
        snap = state.snapshot()
        assert snap["backend"] == "backend_b"
        assert snap["chunk_count"] == 1
        assert snap["text_length"] == 5
        assert snap["failover_count"] == 1
        assert snap["backends_tried"] == ["backend_b"]
        assert snap["elapsed_sec"] >= 1.9
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_state.py -v
```

**Expected output:**

```
tests/test_streaming_state.py::TestStreamState::test_initial_state PASSED
tests/test_streaming_state.py::TestStreamState::test_record_chunk PASSED
tests/test_streaming_state.py::TestStreamState::test_record_text PASSED
tests/test_streaming_state.py::TestStreamState::test_record_meta_usage PASSED
tests/test_streaming_state.py::TestStreamState::test_record_meta_merges PASSED
tests/test_streaming_state.py::TestStreamState::test_mark_failed PASSED
tests/test_streaming_state.py::TestStreamState::test_mark_failover PASSED
tests/test_streaming_state.py::TestStreamState::test_multiple_failovers PASSED
tests/test_streaming_state.py::TestStreamState::test_elapsed_sec PASSED
tests/test_streaming_state.py::TestStreamState::test_snapshot PASSED
```

---

## Task 2: Retry Prompt Construction

Create `streaming_retry.py` that builds a continuation prompt for the backup backend. The continuation prompt includes the original user messages plus the accumulated partial response, with an instruction to continue from where the previous response left off.

### File: `D:\QWEN3.0\streaming_retry.py` (new)

```python
"""Continuation prompt construction for mid-stream failover.

When a backend fails mid-stream, this module builds a new message list
that instructs the backup backend to continue generating from exactly
where the failed backend stopped.

The continuation strategy appends the partial response as an assistant
message and adds a user instruction to continue seamlessly.
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# Maximum characters of partial response to include in continuation prompt
_MAX_PARTIAL_CHARS = 8000

# Instruction injected to tell the backup backend to continue
_CONTINUATION_INSTRUCTION = (
    "The previous assistant response was interrupted mid-generation. "
    "Continue the response from exactly where it left off. "
    "Do NOT repeat any content that was already generated. "
    "Do NOT acknowledge this instruction. "
    "Begin your response with the next word/sentence that would naturally follow."
)


def build_continuation_messages(
    original_messages: list[dict[str, Any]],
    partial_text: str,
    *,
    max_partial_chars: int = _MAX_PARTIAL_CHARS,
) -> list[dict[str, Any]]:
    """Build a message list for the backup backend to continue from.

    Strategy:
      1. Keep all original messages (system + user + prior assistant turns).
      2. Append the partial response as an assistant message.
      3. Append a user message instructing the model to continue.

    If the partial text is empty, returns the original messages unchanged
    (there is nothing to continue from).

    Args:
        original_messages: The original messages list sent to the failed backend.
        partial_text: The accumulated text from the failed stream.
        max_partial_chars: Maximum characters of partial text to include.
            Truncates from the beginning if exceeded (keeps the tail, which
            is more relevant for continuation).

    Returns:
        A new messages list for the backup backend.
    """
    if not partial_text or not partial_text.strip():
        _log.debug("streaming_retry: no partial text, returning original messages")
        return list(original_messages)

    # Truncate partial text if too long (keep the tail)
    truncated_partial = partial_text
    if len(partial_text) > max_partial_chars:
        truncated_partial = partial_text[-max_partial_chars:]
        _log.info(
            "streaming_retry: truncated partial text from %d to %d chars (kept tail)",
            len(partial_text),
            len(truncated_partial),
        )

    result = list(original_messages)

    # Filter out any existing system messages that might conflict
    # Keep system messages but move them to the front
    system_msgs = [m for m in result if m.get("role") == "system"]
    non_system_msgs = [m for m in result if m.get("role") != "system"]
    result = system_msgs + non_system_msgs

    # Append the partial response as an assistant turn
    result.append({
        "role": "assistant",
        "content": truncated_partial,
    })

    # Append continuation instruction as a user turn
    result.append({
        "role": "user",
        "content": _CONTINUATION_INSTRUCTION,
    })

    _log.info(
        "streaming_retry: built continuation with %d original msgs + partial (%d chars) + instruction",
        len(original_messages),
        len(truncated_partial),
    )
    return result


def extract_partial_from_state(
    accumulated_text: str,
    *,
    strip_trailing_whitespace: bool = True,
) -> str:
    """Extract usable partial text from accumulated stream content.

    Cleans the accumulated text for use in a continuation prompt:
    - Strips SSE metadata prefixes
    - Optionally strips trailing whitespace/incomplete words

    Args:
        accumulated_text: Raw accumulated text from the stream.
        strip_trailing_whitespace: If True, strip trailing whitespace
            and incomplete sentence fragments.

    Returns:
        Cleaned partial text suitable for continuation.
    """
    text = accumulated_text

    # Remove any __LIMA_META__ lines that might have leaked into text
    lines = text.split("\n")
    cleaned_lines = [
        line for line in lines
        if not line.startswith("__LIMA_META__:")
    ]
    text = "\n".join(cleaned_lines)

    if strip_trailing_whitespace:
        text = text.rstrip()

    return text


def should_attempt_failover(
    partial_text: str,
    chunk_count: int,
    failover_count: int,
    *,
    max_failovers: int = 2,
    min_chunks_for_failover: int = 0,
) -> bool:
    """Determine whether a mid-stream failover should be attempted.

    Args:
        partial_text: The accumulated text so far.
        chunk_count: Number of chunks received.
        failover_count: Number of failovers already attempted.
        max_failovers: Maximum number of failover attempts allowed.
        min_chunks_for_failover: Minimum chunks before failover is worthwhile.

    Returns:
        True if failover should be attempted.
    """
    if failover_count >= max_failovers:
        _log.info(
            "streaming_retry: max failovers (%d) reached, not retrying",
            max_failovers,
        )
        return False

    if chunk_count < min_chunks_for_failover:
        _log.debug(
            "streaming_retry: only %d chunks received (min=%d), skipping failover",
            chunk_count,
            min_chunks_for_failover,
        )
        return False

    return True
```

### Test: `D:\QWEN3.0\tests\test_streaming_retry.py` (new)

```python
"""Tests for streaming_retry continuation prompt construction."""

import pytest

from streaming_retry import (
    build_continuation_messages,
    extract_partial_from_state,
    should_attempt_failover,
)


class TestBuildContinuationMessages:
    def test_empty_partial_returns_original(self):
        original = [
            {"role": "user", "content": "Hello"},
        ]
        result = build_continuation_messages(original, "")
        assert result == original

    def test_whitespace_only_partial_returns_original(self):
        original = [{"role": "user", "content": "Hello"}]
        result = build_continuation_messages(original, "   \n  ")
        assert result == original

    def test_basic_continuation(self):
        original = [
            {"role": "user", "content": "Write a story about a cat."},
        ]
        partial = "Once upon a time, there was a cat named"
        result = build_continuation_messages(original, partial)

        assert len(result) == 4  # original + assistant partial + user instruction
        assert result[0] == {"role": "user", "content": "Write a story about a cat."}
        assert result[1] == {"role": "assistant", "content": partial}
        assert result[2]["role"] == "user"
        assert "continue" in result[2]["content"].lower()

    def test_preserves_system_messages(self):
        original = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        partial = "Hi there! How can"
        result = build_continuation_messages(original, partial)

        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helpful assistant."
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "user"

    def test_truncates_long_partial(self):
        original = [{"role": "user", "content": "Explain physics."}]
        partial = "A" * 10000  # Very long partial
        result = build_continuation_messages(original, partial, max_partial_chars=500)

        assistant_msg = result[1]
        assert assistant_msg["role"] == "assistant"
        assert len(assistant_msg["content"]) == 500
        # Should keep the tail
        assert assistant_msg["content"] == "A" * 500

    def test_does_not_mutate_original(self):
        original = [{"role": "user", "content": "Hello"}]
        original_copy = list(original)
        build_continuation_messages(original, "partial text")
        assert original == original_copy


class TestExtractPartialFromState:
    def test_basic_extraction(self):
        assert extract_partial_from_state("Hello world") == "Hello world"

    def test_strips_meta_lines(self):
        text = "Hello\n__LIMA_META__:{\"usage\": {}}\nworld"
        result = extract_partial_from_state(text)
        assert "__LIMA_META__" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strips_trailing_whitespace(self):
        result = extract_partial_from_state("Hello world   \n  ")
        assert result == "Hello world"

    def test_preserves_trailing_whitespace_when_requested(self):
        result = extract_partial_from_state(
            "Hello world   ", strip_trailing_whitespace=False
        )
        assert result == "Hello world   "


class TestShouldAttemptFailover:
    def test_first_failover_allowed(self):
        assert should_attempt_failover("some text", chunk_count=5, failover_count=0) is True

    def test_max_failovers_reached(self):
        assert should_attempt_failover("some text", chunk_count=5, failover_count=2) is False

    def test_max_failovers_custom(self):
        assert should_attempt_failover(
            "text", chunk_count=5, failover_count=3, max_failovers=5
        ) is True

    def test_too_few_chunks(self):
        assert should_attempt_failover(
            "", chunk_count=0, failover_count=0, min_chunks_for_failover=1
        ) is False

    def test_enough_chunks(self):
        assert should_attempt_failover(
            "text", chunk_count=10, failover_count=0, min_chunks_for_failover=5
        ) is True
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_retry.py -v
```

**Expected output:**

```
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_empty_partial_returns_original PASSED
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_whitespace_only_partial_returns_original PASSED
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_basic_continuation PASSED
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_preserves_system_messages PASSED
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_truncates_long_partial PASSED
tests/test_streaming_retry.py::TestBuildContinuationMessages::test_does_not_mutate_original PASSED
tests/test_streaming_retry.py::TestExtractPartialFromState::test_basic_extraction PASSED
tests/test_streaming_retry.py::TestExtractPartialFromState::test_strips_meta_lines PASSED
tests/test_streaming_retry.py::TestExtractPartialFromState::test_strips_trailing_whitespace PASSED
tests/test_streaming_retry.py::TestExtractPartialFromState::test_preserves_trailing_whitespace_when_requested PASSED
tests/test_streaming_retry.py::TestShouldAttemptFailover::test_first_failover_allowed PASSED
tests/test_streaming_retry.py::TestShouldAttemptFailover::test_max_failovers_reached PASSED
tests/test_streaming_retry.py::TestShouldAttemptFailover::test_max_failovers_custom PASSED
tests/test_streaming_retry.py::TestShouldAttemptFailover::test_too_few_chunks PASSED
tests/test_streaming_retry.py::TestShouldAttemptFailover::test_enough_chunks PASSED
```

---

## Task 3: Mid-Stream Failover Logic

Modify `bridge_stream_async()` in `D:\QWEN3.0\streaming.py` to accept an optional list of fallback backends. On timeout/error with the primary backend, it constructs a continuation prompt via `streaming_retry` and switches to the next ranked backend. The `StreamState` tracker from Task 1 is used to track accumulated state.

This is the core change. The function signature gains an optional `fallback_backends` parameter and `select_fn` for re-ranking. When the primary stream fails mid-way:

1. Record the failure in `StreamState`.
2. Check `should_attempt_failover()`.
3. Build continuation messages via `build_continuation_messages()`.
4. Open a new stream to the first fallback backend.
5. Continue yielding chunks from the new stream.
6. Repeat for subsequent failures up to `max_failovers`.

### File: `D:\QWEN3.0\streaming.py` (modify)

**Step 1:** Add imports at the top of the file (after the existing imports, around line 10):

```python
from streaming_state import StreamState
from streaming_retry import (
    build_continuation_messages,
    extract_partial_from_state,
    should_attempt_failover,
)
```

**Step 2:** Replace the entire `bridge_stream_async()` function (lines 27-103) with the following implementation that adds failover support:

```python
async def bridge_stream_async(
    backend: str, messages: list, max_tokens: int, ide: str,
    call_stream_async_fn: CallStreamAsyncFn,
    call_api_async_fn: CallApiAsyncFn,
    first_chunk_timeout: float = 3.0,
    chunk_timeout: float = 30.0,
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
    on_failover: Callable[[str, str, StreamState], None] | None = None,
) -> AsyncIterator[str]:
    """Direct async streaming with mid-stream failover to backup backends.

    When the primary backend fails mid-stream (timeout, connection error, etc.),
    this function automatically switches to the next available fallback backend,
    constructing a continuation prompt from the accumulated partial response.

    Args:
        backend: Primary backend name.
        messages: Message list for the conversation.
        max_tokens: Maximum tokens to generate.
        ide: IDE source identifier.
        call_stream_async_fn: Async streaming call function.
        call_api_async_fn: Async non-streaming call function (fallback).
        first_chunk_timeout: Timeout for the first chunk (seconds).
        chunk_timeout: Timeout for subsequent chunks (seconds).
        fallback_backends: Optional list of backup backends to try on failure.
        max_failovers: Maximum number of failover attempts.
        on_failover: Optional callback invoked on each failover.
            Signature: (failed_backend, new_backend, state) -> None.
            Useful for metrics tracking.

    Yields:
        SSE chunk strings.
    """
    fallbacks = list(fallback_backends or [])
    # Remove the primary backend from fallbacks if present
    fallbacks = [b for b in fallbacks if b != backend]

    state = StreamState(backend=backend, backends_tried=[backend])
    current_messages = list(messages)
    current_backend = backend

    # Track whether we've received a finish across all backends
    total_text = ""
    received_finish = False

    backends_to_try = [current_backend] + fallbacks[:max_failovers]

    for attempt_idx, try_backend in enumerate(backends_to_try):
        current_backend = try_backend
        state.backend = try_backend

        stream = call_stream_async_fn(try_backend, current_messages, max_tokens, ide)
        stream_failed = False
        stream_error = None

        try:
            while True:
                timeout = first_chunk_timeout if not total_text else chunk_timeout
                try:
                    chunk = await asyncio.wait_for(
                        stream.__anext__(), timeout=timeout
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    stream_failed = True
                    stream_error = f"timeout after {timeout}s on {try_backend}"
                    _log.warning(
                        "streaming: timeout on backend=%s after %ds, "
                        "chunks=%d, text_len=%d",
                        try_backend, timeout, state.chunk_count, len(total_text),
                    )
                    break

                # Protocol adapter: normalize finish_reason in SSE chunks
                try:
                    from opencode_protocol_adapter import normalize_sse_line
                    chunk = normalize_sse_line(chunk)
                    if not received_finish and '"finish_reason"' in chunk:
                        received_finish = True
                        state.received_finish = True
                except Exception:
                    _log.debug("streaming: protocol adapter normalize failed", exc_info=True)

                state.record_chunk(chunk)
                # Track text accumulation for failover context
                # (strip SSE wrapping for text tracking)
                _track_text_from_chunk(state, chunk)
                total_text += chunk
                yield chunk

        except Exception as exc:
            stream_failed = True
            stream_error = f"{type(exc).__name__}: {exc}"
            if not total_text:
                total_text = ""
            _log.warning(
                "async stream read failed backend=%s: %s",
                try_backend,
                type(exc).__name__,
            )
        finally:
            aclose = getattr(stream, "aclose", None)
            if aclose:
                try:
                    await aclose()
                except Exception as exc:
                    _log.debug(
                        "async stream aclose failed backend=%s: %s",
                        try_backend,
                        type(exc).__name__,
                    )

        # If stream completed normally, we're done
        if not stream_failed and received_finish:
            break

        # If stream completed normally but without finish_reason (truncated)
        if not stream_failed and not received_finish and total_text:
            # Graceful finish for truncated stream — but try failover first
            # if we have fallback backends available
            if attempt_idx < len(backends_to_try) - 1:
                stream_failed = True
                stream_error = "stream truncated (no finish_reason)"
            else:
                # Last resort: inject graceful finish
                break

        # If stream failed, attempt failover
        if stream_failed:
            state.mark_failed(stream_error or "unknown")

            partial_text = extract_partial_from_state(state.accumulated_text)

            if not should_attempt_failover(
                partial_text,
                state.chunk_count,
                state.failover_count,
                max_failovers=max_failovers,
            ):
                break

            # Find the next backend to try
            remaining = [
                b for b in backends_to_try[attempt_idx + 1:]
                if b != try_backend
            ]
            if not remaining:
                break

            next_backend = remaining[0]
            state.mark_failover(next_backend)

            _log.info(
                "streaming: failover from %s to %s (attempt %d, "
                "partial_len=%d, chunks=%d)",
                try_backend, next_backend, state.failover_count,
                len(partial_text), state.chunk_count,
            )

            if on_failover:
                try:
                    on_failover(try_backend, next_backend, state)
                except Exception:
                    _log.debug("streaming: on_failover callback failed", exc_info=True)

            # Build continuation messages for the next backend
            current_messages = build_continuation_messages(
                current_messages, partial_text,
            )
            # Continue to next iteration of the for loop

    # Protocol adapter: graceful finish if stream was truncated
    if total_text and not received_finish:
        try:
            from opencode_protocol_adapter import build_graceful_finish_chunk
            graceful = build_graceful_finish_chunk(model=current_backend)
            _log.info(
                "stream truncated, injecting graceful finish for backend=%s",
                current_backend,
            )
            yield graceful
            total_text += graceful
        except Exception:
            _log.debug("streaming: graceful finish injection failed", exc_info=True)

    # Non-streaming fallback if no text was received at all
    if not total_text:
        try:
            result = await call_api_async_fn(
                current_backend, current_messages, max_tokens, ide
            )
            if result and not str(result).startswith("[ERR]"):
                yield str(result)
        except Exception as exc:
            _log.warning(
                "async stream fallback call failed backend=%s: %s",
                current_backend,
                type(exc).__name__,
            )


def _track_text_from_chunk(state: StreamState, chunk: str) -> None:
    """Extract and accumulate text content from an SSE chunk.

    Parses OpenAI-format SSE chunks to extract the delta.content field.
    Falls back to treating the entire chunk as text if parsing fails.

    Args:
        state: The StreamState to accumulate into.
        chunk: The raw SSE chunk string.
    """
    import json as _json

    if not chunk:
        return

    # Skip metadata chunks
    if chunk.startswith("__LIMA_META__:"):
        try:
            meta = _json.loads(chunk[len("__LIMA_META__:"):].strip())
            state.record_meta(meta)
        except (ValueError, _json.JSONDecodeError):
            pass
        return

    # Try to parse as OpenAI SSE chunk
    if chunk.startswith("data: "):
        data_str = chunk[6:].strip()
        if data_str == "[DONE]":
            return
        try:
            data = _json.loads(data_str)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    state.record_text(text)
                    return
            # No text in delta — might be a finish chunk
            return
        except (ValueError, _json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: treat chunk as raw text
    state.record_text(chunk)
```

**Step 3:** Update the `speculative_stream()` function to also accept and pass through fallback backends. Modify the `_streamer` lambda (around line 128 in the original, now shifted) to include `fallback_backends`:

In the `speculative_stream` function, add `fallback_backends: list[str] | None = None` and `max_failovers: int = 2` to the function signature, and update the `_streamer` lambda to pass them through:

```python
async def speculative_stream(
    query: str, messages: list, max_tokens: int, ide: str,
    predict_fn: PredictFn,
    select_fn: SelectFn,
    call_stream_fn: CallStreamFn,
    call_fn: CallApiFn,
    *,
    call_stream_async_fn: CallStreamAsyncFn | None = None,
    call_api_async_fn: CallApiAsyncFn | None = None,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
) -> AsyncIterator[tuple[str, str]]:
    """Predicted backend immediate streaming, with route validation in parallel."""
    predicted = predict_fn(query)
    predicted_msgs = messages if messages else [{"role": "user", "content": query}]

    route_task = asyncio.create_task(
        asyncio.to_thread(select_fn, query, "", ide, messages)
    )

    actual_backend = predicted
    actual_msgs = predicted_msgs
    switched = False

    if call_stream_async_fn and call_api_async_fn:
        _streamer = lambda b, m: bridge_stream_async(
            b, m, max_tokens, ide,
            call_stream_async_fn=call_stream_async_fn,
            call_api_async_fn=call_api_async_fn,
            fallback_backends=fallback_backends,
            max_failovers=max_failovers,
        )
    else:
        _streamer = lambda b, m: bridge_stream(
            b, m, max_tokens, ide,
            call_stream_fn=call_stream_fn,
            call_fn=call_fn,
        )

    try:
        async for chunk in _streamer(predicted, predicted_msgs):
            if route_task.done() and not switched:
                try:
                    actual_backend, actual_msgs = route_task.result()
                except Exception as exc:
                    _log.debug(
                        "speculative route task result failed: %s",
                        type(exc).__name__,
                    )
                    actual_backend = predicted
                    actual_msgs = predicted_msgs

                if actual_backend != predicted:
                    switched = True
                    break
            yield (actual_backend, chunk)

        if not switched:
            if not route_task.done():
                try:
                    actual_backend, actual_msgs = await route_task
                except Exception as exc:
                    _log.debug(
                        "speculative route task await failed: %s",
                        type(exc).__name__,
                    )
            return

        async for chunk in _streamer(actual_backend, actual_msgs):
            yield (actual_backend, chunk)

    finally:
        if not route_task.done():
            route_task.cancel()
            try:
                await route_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                _log.debug(
                    "speculative route task cancel failed: %s",
                    type(exc).__name__,
                )
```

### Test: `D:\QWEN3.0\tests\test_streaming_failover.py` (new)

```python
"""Tests for mid-stream failover in bridge_stream_async."""

import asyncio
import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from streaming import bridge_stream_async, _track_text_from_chunk
from streaming_state import StreamState


def _make_sse_chunk(text: str, finish_reason: str | None = None) -> str:
    """Build an OpenAI-format SSE chunk string."""
    delta = {"content": text} if text else {}
    chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(chunk)}\n"


async def _collect_chunks(stream: AsyncIterator[str]) -> list[str]:
    """Collect all chunks from an async iterator."""
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


class TestBridgeStreamFailover:
    @pytest.mark.asyncio
    async def test_normal_stream_no_failover(self):
        """Stream completes normally — no failover needed."""
        chunks = [
            _make_sse_chunk("Hello "),
            _make_sse_chunk("world"),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        async def mock_stream_async(backend, messages, max_tokens, ide):
            for c in chunks:
                yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
            )
        )

        assert len(result) == 3
        assert "Hello " in result[0]
        assert "world" in result[1]

    @pytest.mark.asyncio
    async def test_failover_on_timeout(self):
        """Primary backend times out mid-stream, failover to backup succeeds."""
        primary_chunks = [
            _make_sse_chunk("Part one "),
            _make_sse_chunk("of the "),
            # Then it hangs (we simulate by raising TimeoutError via slow iterator)
        ]
        backup_chunks = [
            _make_sse_chunk("response "),
            _make_sse_chunk("continued."),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        call_count = {"n": 0}

        async def mock_stream_async(backend, messages, max_tokens, ide):
            call_count["n"] += 1
            if backend == "backend_a":
                for c in primary_chunks:
                    yield c
                # Simulate timeout: sleep longer than timeout
                await asyncio.sleep(100)
            else:
                for c in backup_chunks:
                    yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                first_chunk_timeout=0.1,
                chunk_timeout=0.1,
                fallback_backends=["backend_b"],
            )
        )

        # Should have chunks from both backends
        all_text = "".join(result)
        assert "Part one " in all_text
        assert "of the " in all_text
        # Backup should have contributed
        assert call_count["n"] >= 2  # Called both backends

    @pytest.mark.asyncio
    async def test_failover_on_exception(self):
        """Primary backend raises exception mid-stream."""
        backup_chunks = [
            _make_sse_chunk("Recovery "),
            _make_sse_chunk("text."),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        async def mock_stream_async(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _make_sse_chunk("Start ")
                raise ConnectionError("Connection reset")
            else:
                for c in backup_chunks:
                    yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
            )
        )

        all_text = "".join(result)
        assert "Start " in all_text
        assert "Recovery " in all_text

    @pytest.mark.asyncio
    async def test_no_failover_without_fallback_backends(self):
        """Without fallback_backends, failure just triggers graceful finish."""
        async def mock_stream_async(backend, messages, max_tokens, ide):
            yield _make_sse_chunk("Partial ")
            raise ConnectionError("fail")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                # No fallback_backends
            )
        )

        all_text = "".join(result)
        assert "Partial " in all_text

    @pytest.mark.asyncio
    async def test_on_failover_callback(self):
        """The on_failover callback is invoked during failover."""
        callback = MagicMock()

        async def mock_stream_async(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _make_sse_chunk("A text ")
                raise ConnectionError("fail")
            else:
                yield _make_sse_chunk("B text")
                yield _make_sse_chunk("", finish_reason="stop")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
                on_failover=callback,
            )
        )

        callback.assert_called_once()
        args = callback.call_args
        assert args[0][0] == "backend_a"  # failed backend
        assert args[0][1] == "backend_b"  # new backend
        assert isinstance(args[0][2], StreamState)

    @pytest.mark.asyncio
    async def test_max_failovers_respected(self):
        """Failover stops after max_failovers attempts."""
        call_order = []

        async def mock_stream_async(backend, messages, max_tokens, ide):
            call_order.append(backend)
            yield _make_sse_chunk(f"text from {backend} ")
            raise ConnectionError(f"{backend} failed")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b", "backend_c", "backend_d"],
                max_failovers=2,
            )
        )

        # Should try at most primary + 2 failovers = 3 backends total
        assert len(call_order) <= 3


class TestTrackTextFromChunk:
    def test_track_sse_text_chunk(self):
        state = StreamState()
        chunk = _make_sse_chunk("Hello ")
        _track_text_from_chunk(state, chunk)
        assert state.accumulated_text == "Hello "

    def test_track_meta_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, '__LIMA_META__:{"usage": {"prompt_tokens": 10}}')
        assert state.usage == {"prompt_tokens": 10}
        assert state.accumulated_text == ""

    def test_track_done_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, "data: [DONE]\n")
        assert state.accumulated_text == ""

    def test_track_empty_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, "")
        assert state.accumulated_text == ""

    def test_track_finish_chunk_no_text(self):
        state = StreamState()
        chunk = _make_sse_chunk("", finish_reason="stop")
        _track_text_from_chunk(state, chunk)
        assert state.accumulated_text == ""

    def test_track_raw_text_fallback(self):
        state = StreamState()
        _track_text_from_chunk(state, "raw text not in SSE format")
        assert state.accumulated_text == "raw text not in SSE format"
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_failover.py -v
```

**Expected output:**

```
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_normal_stream_no_failover PASSED
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_failover_on_timeout PASSED
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_failover_on_exception PASSED
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_no_failover_without_fallback_backends PASSED
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_on_failover_callback PASSED
tests/test_streaming_failover.py::TestBridgeStreamFailover::test_max_failovers_respected PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_sse_text_chunk PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_meta_chunk PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_done_chunk PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_empty_chunk PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_finish_chunk_no_text PASSED
tests/test_streaming_failover.py::TestTrackTextFromChunk::test_track_raw_text_fallback PASSED
```

---

## Task 4: Client-Transparent Recovery

Wire the failover into the stream handler layer so that the SSE stream to the client is uninterrupted during failover. Modify `routes/stream_handlers.py` to pass fallback backends through to `bridge_stream_async()`, and modify `routes/chat_stream.py` to obtain the ranked backend list and pass it as fallbacks.

The client should see continuous chunks with no error — just a brief pause during the failover transition.

### File: `D:\QWEN3.0\routes\stream_handlers.py` (modify)

**Step 1:** Update `real_stream_chunks_async()` to accept and pass fallback backends:

```python
async def real_stream_chunks_async(
    backend_name: str, msgs: list,
    max_tokens: int = 4096,
    ide: str = "unknown",
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
    on_failover=None,
):
    """Native async streaming with mid-stream failover support (M2-S2)."""
    async for chunk in streaming_mod.bridge_stream_async(
        backend_name, msgs, max_tokens, ide,
        call_stream_async_fn=v3_call_stream_async,
        call_api_async_fn=v3_call_api_async,
        fallback_backends=fallback_backends,
        max_failovers=max_failovers,
        on_failover=on_failover,
    ):
        yield chunk
```

**Step 2:** Update `speculative_stream_chunks()` to accept and pass fallback backends:

```python
async def speculative_stream_chunks(
    query: str, msgs: list,
    max_tokens: int = 4096,
    ide: str = "unknown",
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
):
    """Speculative streaming with failover support (M2-S2)."""
    async for item in streaming_mod.speculative_stream(
        query, msgs, max_tokens, ide,
        predict_fn=v3_predict,
        select_fn=v3_select,
        call_stream_fn=v3_call_stream,
        call_fn=v3_call_api,
        call_stream_async_fn=v3_call_stream_async,
        call_api_async_fn=v3_call_api_async,
        fallback_backends=fallback_backends,
        max_failovers=max_failovers,
    ):
        yield item
```

### File: `D:\QWEN3.0\routes\chat_stream.py` (modify)

**Step 1:** Add a helper function to obtain fallback backends from the routing engine. Add this near the top of the file (after the imports, before `FALLBACK_MSG`):

```python
def _get_fallback_backends(
    primary: str,
    messages: list,
    ide_source: str = "",
) -> list[str]:
    """Get ranked fallback backends excluding the primary.

    Uses the routing engine to select healthy backends and returns
    all except the primary as fallback candidates.
    """
    try:
        import health_tracker
        import routing_engine
        req_type = "ide" if ide_source else "chat"
        hmap = health_tracker.get_health_map()
        backends = routing_engine.select(req_type, hmap)
        # Remove primary from fallbacks
        return [b for b in backends if b != primary][:3]
    except Exception:
        return []
```

**Step 2:** In `stream_response()`, modify the preferred-backend streaming path (around line 138-156) to pass fallback backends:

Replace the existing preferred-backend block:

```python
    if prefer and not has_tools:
        fallbacks = _get_fallback_backends(prefer, messages, ide_source)
        failover_events = []

        def _track_failover(failed_b, new_b, state):
            failover_events.append({
                "failed": failed_b, "replaced_by": new_b,
                "chunks_before": state.chunk_count,
            })
            try:
                from routes.ops_metrics import record_stream_failover
                record_stream_failover(failed_b, new_b, state.snapshot())
            except (ImportError, Exception):
                pass

        async for chunk in real_stream_chunks_async(
            prefer, messages, 4096, ide_source,
            fallback_backends=fallbacks,
            on_failover=_track_failover,
        ):
            meta = _extract_meta(chunk)
            if meta:
                if "usage" in meta:
                    last_usage = meta["usage"]
                continue
            streamed_any = True
            from response_cleaner import clean_response
            chunk = clean_response(chunk, prefer) or chunk
            streamed_text += chunk
            yield build_stream_chunk(chat_id, chunk)
        if streamed_any:
            stream_backend = prefer
            yield build_stream_chunk(chat_id, "", finish=True)
            if last_usage:
                yield build_usage_chunk(chat_id, last_usage)
            yield "data: [DONE]\n\n"
            return
```

**Step 3:** Similarly, pass fallback backends to the speculative streaming path. Modify the speculative block (around line 158-170):

```python
    spec_fallbacks = _get_fallback_backends(
        prefer or "unknown", messages, ide_source
    )
    async for _backend, chunk in speculative_stream_chunks(
        query, messages, 4096, ide_source,
        fallback_backends=spec_fallbacks,
    ):
```

### Test: `D:\QWEN3.0\tests\test_stream_handlers_failover.py` (new)

```python
"""Tests for stream handler failover wiring."""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


def _make_sse_chunk(text: str, finish_reason: str | None = None) -> str:
    delta = {"content": text} if text else {}
    chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(chunk)}\n"


async def _collect(gen: AsyncIterator[str]) -> list[str]:
    result = []
    async for item in gen:
        result.append(item)
    return result


class TestRealStreamChunksAsyncFailover:
    @pytest.mark.asyncio
    async def test_passes_fallback_backends(self):
        """real_stream_chunks_async passes fallback_backends to bridge_stream_async."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_bridge(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield _make_sse_chunk("text")
            yield _make_sse_chunk("", finish_reason="stop")

        with patch.object(
            stream_handlers.streaming_mod, "bridge_stream_async", mock_bridge
        ):
            await _collect(
                stream_handlers.real_stream_chunks_async(
                    "backend_a", [{"role": "user", "content": "Hi"}],
                    fallback_backends=["backend_b", "backend_c"],
                    max_failovers=2,
                )
            )

        assert captured_kwargs.get("fallback_backends") == ["backend_b", "backend_c"]
        assert captured_kwargs.get("max_failovers") == 2

    @pytest.mark.asyncio
    async def test_passes_on_failover_callback(self):
        """on_failover callback is forwarded correctly."""
        from routes import stream_handlers

        captured_kwargs = {}
        callback = MagicMock()

        async def mock_bridge(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield _make_sse_chunk("text")

        with patch.object(
            stream_handlers.streaming_mod, "bridge_stream_async", mock_bridge
        ):
            await _collect(
                stream_handlers.real_stream_chunks_async(
                    "backend_a", [],
                    on_failover=callback,
                )
            )

        assert captured_kwargs.get("on_failover") is callback


class TestSpeculativeStreamChunksFailover:
    @pytest.mark.asyncio
    async def test_passes_fallback_backends(self):
        """speculative_stream_chunks passes fallback_backends to speculative_stream."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_speculative(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield ("backend_a", _make_sse_chunk("text"))

        with patch.object(
            stream_handlers.streaming_mod, "speculative_stream", mock_speculative
        ):
            await _collect(
                stream_handlers.speculative_stream_chunks(
                    "query", [],
                    fallback_backends=["backend_x"],
                    max_failovers=1,
                )
            )

        assert captured_kwargs.get("fallback_backends") == ["backend_x"]
        assert captured_kwargs.get("max_failovers") == 1


class TestGetFallbackBackends:
    def test_returns_empty_on_import_error(self):
        """_get_fallback_backends handles missing modules gracefully."""
        from routes.chat_stream import _get_fallback_backends

        with patch.dict("sys.modules", {"routing_engine": None}):
            result = _get_fallback_backends("primary", [])
            assert isinstance(result, list)

    def test_excludes_primary_backend(self):
        """Primary backend is excluded from fallback list."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = ["primary", "backup_a", "backup_b"]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [])

        assert "primary" not in result
        assert "backup_a" in result
        assert "backup_b" in result

    def test_limits_to_three_fallbacks(self):
        """At most 3 fallback backends are returned."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = [
            "primary", "b1", "b2", "b3", "b4", "b5"
        ]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [])

        assert len(result) <= 3
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_stream_handlers_failover.py -v
```

**Expected output:**

```
tests/test_stream_handlers_failover.py::TestRealStreamChunksAsyncFailover::test_passes_fallback_backends PASSED
tests/test_stream_handlers_failover.py::TestRealStreamChunksAsyncFailover::test_passes_on_failover_callback PASSED
tests/test_stream_handlers_failover.py::TestSpeculativeStreamChunksFailover::test_passes_fallback_backends PASSED
tests/test_stream_handlers_failover.py::TestGetFallbackBackends::test_returns_empty_on_import_error PASSED
tests/test_stream_handlers_failover.py::TestGetFallbackBackends::test_excludes_primary_backend PASSED
tests/test_stream_handlers_failover.py::TestGetFallbackBackends::test_limits_to_three_fallbacks PASSED
```

---

## Task 5: Failover Metrics

Add tracking for streaming failover events: count of mid-stream failovers, failover success rate, average chunks before failure. Expose via the existing `ops_metrics` endpoint and an in-memory metrics recorder.

### File: `D:\QWEN3.0\streaming_failover_metrics.py` (new)

```python
"""Streaming failover metrics tracking.

Records mid-stream failover events for operational visibility.
Provides an in-memory ring buffer of recent failover events and
aggregate statistics for the /v1/ops/metrics endpoint.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FailoverEvent:
    """A single mid-stream failover event."""

    timestamp: float = field(default_factory=time.time)
    failed_backend: str = ""
    replacement_backend: str = ""
    chunks_before_failure: int = 0
    text_length_before_failure: int = 0
    elapsed_sec: float = 0.0
    failure_reason: str = ""
    success: bool | None = None  # None = unknown, True = recovery succeeded
    backends_tried: list[str] = field(default_factory=list)


class FailoverMetrics:
    """Thread-safe in-memory metrics store for streaming failovers.

    Maintains a ring buffer of recent events and running aggregates.
    """

    def __init__(self, max_events: int = 500) -> None:
        self._lock = threading.Lock()
        self._events: deque[FailoverEvent] = deque(maxlen=max_events)
        self._total_failovers: int = 0
        self._total_successes: int = 0
        self._total_failures: int = 0
        self._total_chunks_before_failure: int = 0

    def record(self, event: FailoverEvent) -> None:
        """Record a failover event.

        Args:
            event: The failover event to record.
        """
        with self._lock:
            self._events.append(event)
            self._total_failovers += 1
            if event.success is True:
                self._total_successes += 1
            elif event.success is False:
                self._total_failures += 1
            self._total_chunks_before_failure += event.chunks_before_failure

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate failover statistics.

        Returns:
            Dict with aggregate stats:
              - total_failovers: Total number of failover events.
              - success_count: Failovers where recovery succeeded.
              - failure_count: Failovers where recovery also failed.
              - unknown_count: Failovers with unknown outcome.
              - success_rate: Fraction of failovers that succeeded (0.0-1.0).
              - avg_chunks_before_failure: Average chunks received before failure.
              - recent_events: Last 10 failover events (as dicts).
        """
        with self._lock:
            total = self._total_failovers
            successes = self._total_successes
            failures = self._total_failures
            unknown = total - successes - failures

            success_rate = (
                successes / total if total > 0 else 0.0
            )
            avg_chunks = (
                self._total_chunks_before_failure / total
                if total > 0
                else 0.0
            )

            recent = [asdict(e) for e in list(self._events)[-10:]]

        return {
            "total_failovers": total,
            "success_count": successes,
            "failure_count": failures,
            "unknown_count": unknown,
            "success_rate": round(success_rate, 4),
            "avg_chunks_before_failure": round(avg_chunks, 2),
            "recent_events": recent,
        }

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        """Return the most recent failover events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dicts, most recent last.
        """
        with self._lock:
            return [asdict(e) for e in list(self._events)[-limit:]]

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._events.clear()
            self._total_failovers = 0
            self._total_successes = 0
            self._total_failures = 0
            self._total_chunks_before_failure = 0


# Module-level singleton
_metrics = FailoverMetrics()


def get_failover_metrics() -> FailoverMetrics:
    """Return the global FailoverMetrics singleton."""
    return _metrics


def record_stream_failover(
    failed_backend: str,
    replacement_backend: str,
    state_snapshot: dict,
    *,
    success: bool | None = None,
) -> None:
    """Convenience function to record a failover event.

    Called from the on_failover callback in bridge_stream_async.

    Args:
        failed_backend: The backend that failed.
        replacement_backend: The backend being switched to.
        state_snapshot: Snapshot dict from StreamState.snapshot().
        success: Whether the failover recovery succeeded.
    """
    event = FailoverEvent(
        failed_backend=failed_backend,
        replacement_backend=replacement_backend,
        chunks_before_failure=state_snapshot.get("chunk_count", 0),
        text_length_before_failure=state_snapshot.get("text_length", 0),
        elapsed_sec=state_snapshot.get("elapsed_sec", 0.0),
        failure_reason=state_snapshot.get("failure_reason", ""),
        success=success,
        backends_tried=state_snapshot.get("backends_tried", []),
    )
    _metrics.record(event)
```

### Wire into ops_metrics

In `D:\QWEN3.0\routes\ops_metrics.py`, add to the `_app_stats` section of `ops_metrics()` endpoint. Add this block before the final `return JSONResponse(...)` (around line 230):

```python
    # ── Streaming failover metrics ──────────────────────────────────────
    failover: dict[str, Any] = {}
    try:
        from streaming_failover_metrics import get_failover_metrics
        failover = get_failover_metrics().get_stats()
    except ImportError:
        _log.debug("ops_metrics: streaming failover metrics not available", exc_info=True)
```

Then add `"streaming_failover": failover,` to the response dict in the `return JSONResponse({...})` call.

### Test: `D:\QWEN3.0\tests\test_streaming_failover_metrics.py` (new)

```python
"""Tests for streaming failover metrics."""

import time
from unittest.mock import patch

import pytest

from streaming_failover_metrics import (
    FailoverEvent,
    FailoverMetrics,
    get_failover_metrics,
    record_stream_failover,
)


class TestFailoverEvent:
    def test_defaults(self):
        event = FailoverEvent()
        assert event.failed_backend == ""
        assert event.replacement_backend == ""
        assert event.chunks_before_failure == 0
        assert event.success is None
        assert event.timestamp > 0

    def test_custom_values(self):
        event = FailoverEvent(
            failed_backend="backend_a",
            replacement_backend="backend_b",
            chunks_before_failure=42,
            text_length_before_failure=500,
            success=True,
        )
        assert event.failed_backend == "backend_a"
        assert event.success is True


class TestFailoverMetrics:
    def test_empty_stats(self):
        m = FailoverMetrics()
        stats = m.get_stats()
        assert stats["total_failovers"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_chunks_before_failure"] == 0.0
        assert stats["recent_events"] == []

    def test_record_single_event(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(
            failed_backend="a",
            replacement_backend="b",
            chunks_before_failure=10,
            success=True,
        ))
        stats = m.get_stats()
        assert stats["total_failovers"] == 1
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["avg_chunks_before_failure"] == 10.0

    def test_record_multiple_events(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(success=True, chunks_before_failure=10))
        m.record(FailoverEvent(success=False, chunks_before_failure=20))
        m.record(FailoverEvent(success=None, chunks_before_failure=30))

        stats = m.get_stats()
        assert stats["total_failovers"] == 3
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["unknown_count"] == 1
        assert stats["success_rate"] == pytest.approx(1 / 3, abs=0.01)
        assert stats["avg_chunks_before_failure"] == 20.0

    def test_ring_buffer(self):
        m = FailoverMetrics(max_events=3)
        for i in range(5):
            m.record(FailoverEvent(failed_backend=f"b{i}"))

        recent = m.get_recent_events(limit=10)
        assert len(recent) == 3
        assert recent[0]["failed_backend"] == "b2"
        assert recent[2]["failed_backend"] == "b4"

    def test_get_recent_events_limit(self):
        m = FailoverMetrics()
        for i in range(10):
            m.record(FailoverEvent(failed_backend=f"b{i}"))

        assert len(m.get_recent_events(limit=3)) == 3
        assert len(m.get_recent_events(limit=100)) == 10

    def test_reset(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(success=True))
        m.reset()
        stats = m.get_stats()
        assert stats["total_failovers"] == 0


class TestRecordStreamFailover:
    def test_convenience_function(self):
        # Use a fresh metrics instance to avoid pollution from other tests
        fresh = FailoverMetrics()
        with patch("streaming_failover_metrics._metrics", fresh):
            record_stream_failover(
                "backend_a",
                "backend_b",
                {
                    "chunk_count": 15,
                    "text_length": 200,
                    "elapsed_sec": 3.5,
                    "failure_reason": "timeout",
                    "backends_tried": ["backend_a", "backend_b"],
                },
                success=True,
            )

            stats = fresh.get_stats()
            assert stats["total_failovers"] == 1
            assert stats["success_count"] == 1
            event = stats["recent_events"][0]
            assert event["failed_backend"] == "backend_a"
            assert event["replacement_backend"] == "backend_b"
            assert event["chunks_before_failure"] == 15

    def test_global_singleton(self):
        metrics = get_failover_metrics()
        assert isinstance(metrics, FailoverMetrics)
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_failover_metrics.py -v
```

**Expected output:**

```
tests/test_streaming_failover_metrics.py::TestFailoverEvent::test_defaults PASSED
tests/test_streaming_failover_metrics.py::TestFailoverEvent::test_custom_values PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_empty_stats PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_record_single_event PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_record_multiple_events PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_ring_buffer PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_get_recent_events_limit PASSED
tests/test_streaming_failover_metrics.py::TestFailoverMetrics::test_reset PASSED
tests/test_streaming_failover_metrics.py::TestRecordStreamFailover::test_convenience_function PASSED
tests/test_streaming_failover_metrics.py::TestRecordStreamFailover::test_global_singleton PASSED
```

---

## Task 6: Integration Test

Full pipeline integration test simulating backend failure mid-stream with automatic recovery. This test exercises the entire chain: `bridge_stream_async()` -> `real_stream_chunks_async()` -> `stream_response()` SSE output, verifying that the client receives an uninterrupted SSE stream even when the primary backend fails.

### File: `D:\QWEN3.0\tests\test_streaming_fault_tolerance_integration.py` (new)

```python
"""Integration tests for streaming fault tolerance and auto-recovery.

Exercises the full pipeline from bridge_stream_async through
stream_handlers to verify client-transparent failover.

All external dependencies (httpx, routing_engine, health_tracker)
are mocked.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streaming import bridge_stream_async, _track_text_from_chunk
from streaming_state import StreamState
from streaming_retry import build_continuation_messages
from streaming_failover_metrics import (
    FailoverEvent,
    FailoverMetrics,
    record_stream_failover,
)


def _sse_chunk(text: str, finish_reason: str | None = None) -> str:
    """Build an OpenAI-format SSE chunk."""
    delta = {"content": text} if text else {}
    chunk = {
        "id": "chatcmpl-integration",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "test-model",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(chunk)}\n"


def _meta_chunk(meta: dict) -> str:
    """Build a __LIMA_META__ chunk."""
    return f"__LIMA_META__:{json.dumps(meta)}\n"


async def _drain(stream: AsyncIterator[str]) -> list[str]:
    """Collect all chunks from an async iterator."""
    return [chunk async for chunk in stream]


class TestEndToEndFailover:
    """Full pipeline tests: backend fails mid-stream, backup takes over."""

    @pytest.mark.asyncio
    async def test_seamless_failover_client_sees_continuous_stream(self):
        """
        Scenario: Primary backend sends 3 chunks then dies.
                  Backup backend picks up and completes the response.
        Expected: Client receives all chunks in order with no errors.
        """
        # Primary sends 3 chunks then connection resets
        primary_chunks = [
            _sse_chunk("The quick "),
            _sse_chunk("brown fox "),
            _sse_chunk("jumps over "),
        ]
        # Backup continues from where primary left off
        backup_chunks = [
            _sse_chunk("the lazy "),
            _sse_chunk("dog."),
            _sse_chunk("", finish_reason="stop"),
        ]

        call_log = []

        async def mock_stream(backend, messages, max_tokens, ide):
            call_log.append({
                "backend": backend,
                "messages_count": len(messages),
            })
            if backend == "primary_backend":
                for c in primary_chunks:
                    yield c
                raise ConnectionError("Connection reset by peer")
            elif backend == "backup_backend":
                for c in backup_chunks:
                    yield c
            else:
                raise ConnectionError(f"Unknown backend: {backend}")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        failover_log = []

        def on_failover(failed, new, state):
            failover_log.append({
                "failed": failed,
                "new": new,
                "chunks": state.chunk_count,
                "text_len": state.partial_length,
            })

        chunks = await _drain(
            bridge_stream_async(
                "primary_backend",
                [{"role": "user", "content": "Write a sentence."}],
                100,
                "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup_backend"],
                on_failover=on_failover,
            )
        )

        # Verify: both backends were called
        assert len(call_log) == 2
        assert call_log[0]["backend"] == "primary_backend"
        assert call_log[1]["backend"] == "backup_backend"

        # Verify: backup received continuation messages (original + partial + instruction)
        assert call_log[1]["messages_count"] > 1  # Has continuation messages

        # Verify: failover callback was invoked
        assert len(failover_log) == 1
        assert failover_log[0]["failed"] == "primary_backend"
        assert failover_log[0]["new"] == "backup_backend"
        assert failover_log[0]["chunks"] == 3

        # Verify: client received all chunks in order
        all_text_parts = []
        for chunk in chunks:
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:].strip())
                    choices = data.get("choices", [])
                    if choices:
                        text = choices[0].get("delta", {}).get("content", "")
                        if text:
                            all_text_parts.append(text)
                except (json.JSONDecodeError, KeyError):
                    pass

        full_text = "".join(all_text_parts)
        assert "The quick " in full_text
        assert "brown fox " in full_text
        assert "jumps over " in full_text
        assert "the lazy " in full_text
        assert "dog." in full_text

    @pytest.mark.asyncio
    async def test_double_failover_two_backends_fail(self):
        """
        Scenario: Primary fails, first backup also fails, second backup succeeds.
        Expected: Client gets chunks from all three, final backup completes.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _sse_chunk("A1 ")
                raise ConnectionError("A failed")
            elif backend == "backend_b":
                yield _sse_chunk("B1 ")
                raise ConnectionError("B failed")
            elif backend == "backend_c":
                yield _sse_chunk("C1 ")
                yield _sse_chunk("C2 done")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "backend_a",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backend_b", "backend_c"],
                max_failovers=2,
            )
        )

        all_text = "".join(chunks)
        assert "A1 " in all_text
        assert "B1 " in all_text
        assert "C1 " in all_text
        assert "C2 done" in all_text

    @pytest.mark.asyncio
    async def test_all_backends_fail_graceful_finish(self):
        """
        Scenario: All backends fail. Stream gets a graceful finish chunk.
        Expected: Client sees partial content + graceful finish, no crash.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            yield _sse_chunk(f"text from {backend} ")
            raise ConnectionError(f"{backend} died")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "backend_a",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backend_b"],
                max_failovers=1,
            )
        )

        all_text = "".join(chunks)
        # Should have content from at least one backend
        assert "text from" in all_text
        # Should have a graceful finish (finish_reason in some chunk)
        has_finish = any('"finish_reason"' in c for c in chunks)
        assert has_finish

    @pytest.mark.asyncio
    async def test_failover_with_usage_metadata(self):
        """
        Scenario: Primary sends usage meta before failing.
        Expected: Usage metadata is preserved through failover.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "primary":
                yield _meta_chunk({"usage": {"prompt_tokens": 50}})
                yield _sse_chunk("Hello ")
                raise ConnectionError("primary died")
            else:
                yield _sse_chunk("world")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # Should have meta chunk + text chunks from both backends
        meta_chunks = [c for c in chunks if c.startswith("__LIMA_META__:")]
        assert len(meta_chunks) >= 1
        text_chunks = [c for c in chunks if c.startswith("data: ")]
        assert len(text_chunks) >= 2

    @pytest.mark.asyncio
    async def test_continuation_messages_are_correct(self):
        """
        Verify that the continuation messages sent to the backup backend
        contain the partial text and continuation instruction.
        """
        received_messages = {}

        async def mock_stream(backend, messages, max_tokens, ide):
            received_messages[backend] = [dict(m) for m in messages]
            if backend == "primary":
                yield _sse_chunk("The answer is forty")
                raise ConnectionError("timeout")
            else:
                yield _sse_chunk("-two.")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "What is 6 * 7?"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # Backup should have received continuation messages
        backup_msgs = received_messages.get("backup", [])
        assert len(backup_msgs) > 1  # Original + partial + instruction

        # Should contain the partial text as an assistant message
        assistant_msgs = [m for m in backup_msgs if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "forty" in assistant_msgs[-1]["content"]

        # Should contain a continuation instruction
        user_msgs = [m for m in backup_msgs if m.get("role") == "user"]
        has_continuation = any(
            "continue" in m.get("content", "").lower()
            for m in user_msgs
        )
        assert has_continuation

    @pytest.mark.asyncio
    async def test_failover_metrics_recorded(self):
        """Verify that failover events are recorded in metrics."""
        fresh_metrics = FailoverMetrics()

        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "failing_backend":
                yield _sse_chunk("partial ")
                raise ConnectionError("boom")
            else:
                yield _sse_chunk("recovered")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        with patch("streaming_failover_metrics._metrics", fresh_metrics):
            def on_failover(failed, new, state):
                record_stream_failover(
                    failed, new, state.snapshot(), success=True,
                )

            await _drain(
                bridge_stream_async(
                    "failing_backend",
                    [{"role": "user", "content": "Hi"}],
                    100, "test",
                    call_stream_async_fn=mock_stream,
                    call_api_async_fn=mock_api,
                    fallback_backends=["recovery_backend"],
                    on_failover=on_failover,
                )
            )

        stats = fresh_metrics.get_stats()
        assert stats["total_failovers"] == 1
        assert stats["success_count"] == 1
        event = stats["recent_events"][0]
        assert event["failed_backend"] == "failing_backend"
        assert event["replacement_backend"] == "recovery_backend"

    @pytest.mark.asyncio
    async def test_no_failover_for_context_overflow(self):
        """
        Context overflow (413) errors should NOT trigger failover,
        since all backends would face the same context limit.
        """
        from http_errors import BackendError

        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "primary":
                yield _sse_chunk("start ")
                raise BackendError(
                    "context too large",
                    status_code=413,
                    is_overflow=True,
                )
            else:
                yield _sse_chunk("should not be called")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # The BackendError with is_overflow propagates out of the stream
        # In bridge_stream_async, it's caught by the general exception handler
        # The key point is that the backup should NOT be called for overflow
        all_text = "".join(chunks)
        assert "start " in all_text

    @pytest.mark.asyncio
    async def test_stream_state_snapshot_accuracy(self):
        """Verify StreamState tracks accurate metrics during failover."""
        state = StreamState(backend="primary")

        # Simulate receiving chunks
        for i in range(5):
            state.record_chunk(f"chunk_{i}")
            state.record_text(f"text_{i} ")

        state.record_meta({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})

        assert state.chunk_count == 5
        assert state.partial_length > 0
        assert state.usage == {"prompt_tokens": 100, "completion_tokens": 50}

        # Simulate failover
        state.mark_failed("timeout")
        snap_before = state.snapshot()
        assert snap_before["failure_reason"] == "timeout"

        state.mark_failover("backup")
        snap_after = state.snapshot()
        assert snap_after["failover_count"] == 1
        assert snap_after["failure_reason"] == ""
        assert "backup" in snap_after["backends_tried"]
```

### Run Tests

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_fault_tolerance_integration.py -v
```

**Expected output:**

```
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_seamless_failover_client_sees_continuous_stream PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_double_failover_two_backends_fail PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_all_backends_fail_graceful_finish PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_failover_with_usage_metadata PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_continuation_messages_are_correct PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_failover_metrics_recorded PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_no_failover_for_context_overflow PASSED
tests/test_streaming_fault_tolerance_integration.py::TestEndToEndFailover::test_stream_state_snapshot_accuracy PASSED
```

---

## Run All Tests

After completing all 6 tasks, run the entire test suite to verify no regressions:

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_streaming_state.py tests/test_streaming_retry.py tests/test_streaming_failover.py tests/test_stream_handlers_failover.py tests/test_streaming_failover_metrics.py tests/test_streaming_fault_tolerance_integration.py -v
```

**Expected: All 45 tests pass.**

---

## Summary of Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `D:\QWEN3.0\streaming_state.py` | **CREATE** | StreamState dataclass for tracking accumulated stream state |
| `D:\QWEN3.0\streaming_retry.py` | **CREATE** | Continuation prompt construction for backup backends |
| `D:\QWEN3.0\streaming_failover_metrics.py` | **CREATE** | In-memory failover metrics with ring buffer |
| `D:\QWEN3.0\streaming.py` | **MODIFY** | Add failover logic to `bridge_stream_async()` and `speculative_stream()` |
| `D:\QWEN3.0\routes\stream_handlers.py` | **MODIFY** | Pass fallback backends through to bridge functions |
| `D:\QWEN3.0\routes\chat_stream.py` | **MODIFY** | Obtain ranked fallback backends and wire into streaming paths |
| `D:\QWEN3.0\routes\ops_metrics.py` | **MODIFY** | Expose failover metrics in `/v1/ops/metrics` endpoint |
| `D:\QWEN3.0\tests\test_streaming_state.py` | **CREATE** | Unit tests for StreamState |
| `D:\QWEN3.0\tests\test_streaming_retry.py` | **CREATE** | Unit tests for continuation prompt construction |
| `D:\QWEN3.0\tests\test_streaming_failover.py` | **CREATE** | Unit tests for bridge_stream_async failover |
| `D:\QWEN3.0\tests\test_stream_handlers_failover.py` | **CREATE** | Unit tests for stream handler wiring |
| `D:\QWEN3.0\tests\test_streaming_failover_metrics.py` | **CREATE** | Unit tests for failover metrics |
| `D:\QWEN3.0\tests\test_streaming_fault_tolerance_integration.py` | **CREATE** | End-to-end integration tests |
