"""Iterator wrappers for Responses SSE stream conversion."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from converters.responses_stream import ResponsesStreamConverter, parse_chat_sse_line


async def transform_chat_sse_stream(
    source: AsyncIterator[bytes | str],
    *,
    model: str = "lima-1.3",
) -> AsyncIterator[str]:
    converter = ResponsesStreamConverter(model=model)
    for ev in converter.bootstrap_events():
        yield ev
    async for raw in source:
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        for part in line.split("\n"):
            chunk = parse_chat_sse_line(part)
            if not chunk:
                continue
            if chunk.get("__done__"):
                for ev in converter.completion_events():
                    yield ev
                return
            for ev in converter.feed_chat_chunk(chunk):
                yield ev
            if converter.failed:
                return
    for ev in converter.completion_events():
        yield ev


def transform_chat_sse_iter(
    lines: Iterator[str],
    *,
    model: str = "lima-1.3",
) -> Iterator[str]:
    converter = ResponsesStreamConverter(model=model)
    for ev in converter.bootstrap_events():
        yield ev
    for line in lines:
        chunk = parse_chat_sse_line(line)
        if not chunk:
            continue
        if chunk.get("__done__"):
            for ev in converter.completion_events():
                yield ev
            return
        for ev in converter.feed_chat_chunk(chunk):
            yield ev
        if converter.failed:
            return
    for ev in converter.completion_events():
        yield ev
