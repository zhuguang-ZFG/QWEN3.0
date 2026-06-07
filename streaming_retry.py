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
