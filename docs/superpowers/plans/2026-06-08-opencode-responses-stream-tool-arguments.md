# OpenCode Responses Stream Tool Arguments Plan

**Goal:** Keep streamed Responses function-call argument deltas string-shaped
even when an upstream Chat Completions stream sends structured values.

## Problem

`ResponsesStreamConverter._feed_tool_delta()` assumes
`delta.tool_calls[].function.arguments` is a string. A non-string value can
raise during concatenation or emit a non-string
`response.function_call_arguments.delta`, which is not compatible with
OpenCode's Responses parser.

## Design

- Add a small parser helper that converts argument deltas to strings.
- Preserve existing string deltas unchanged.
- Serialize structured values as compact JSON.

## Verification

- Add stream conversion coverage for object argument deltas.
- Re-run the Responses/OpenCode focused test slice and ruff.
