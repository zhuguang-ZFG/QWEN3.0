# OpenCode Responses Input Tool Arguments Plan

**Goal:** Normalize Responses input `function_call.arguments` when downgrading
to Chat Completions.

## Problem

The outbound non-stream and stream Responses conversions now normalize
function-call arguments to strings. The inbound Responses-to-Chat conversion
still passes `function_call.arguments` through unchanged, which can produce an
invalid Chat Completions `tool_calls[].function.arguments` value if a client
sends a structured object.

## Design

- Reuse the existing compact argument serialization helper.
- Preserve string arguments unchanged.
- Serialize structured arguments to compact JSON.

## Verification

- Add focused conversion coverage for structured input arguments.
- Re-run the Responses/OpenCode focused test slice and ruff.
