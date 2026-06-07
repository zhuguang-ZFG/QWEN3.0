# OpenCode Responses Incomplete Finish Plan

**Goal:** Preserve truncated or filtered finish reasons when LiMa converts Chat SSE into OpenAI Responses SSE for OpenCode.

## Problem

OpenCode's Responses parser maps `response.incomplete` with `incomplete_details.reason` into finish reasons such as `length` and `content-filter`. LiMa currently ignores Chat SSE `choices[].finish_reason` and always emits `response.completed`, so a context/output limit stop can look like a normal completion to OpenCode.

## Design

- Track the first non-empty Chat `finish_reason`.
- Emit `response.incomplete` when the reason maps to a Responses incomplete reason:
  - `length` -> `max_output_tokens`
  - `content_filter` -> `content_filter`
- Keep normal stop/tool-call finishes as `response.completed`.
- Preserve existing output item completion and usage events.

## Verification

- Add a regression test for Chat SSE `finish_reason="length"`.
- Run the Responses/OpenCode focused pytest slice.
- Run ruff on touched files.
