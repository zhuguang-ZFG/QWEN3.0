# OpenCode Responses Non-Stream Output Normalization Plan

**Goal:** Ensure non-stream shimmed Responses output fields obey Responses
string shape requirements even when upstream Chat Completions returns structured
values.

## Problem

`chat_completion_to_response()` assumes assistant `message.content` and
function-call `arguments` are already strings. Some backends can return content
blocks or decoded argument objects, which would make `output_text.text` or
`function_call.arguments` non-string in the Responses object.

## Design

- Convert assistant message content through the existing `content_to_text()`.
- Serialize non-string function arguments to compact JSON.
- Preserve current behavior for already-string values.

## Verification

- Add non-stream tests for structured content and object arguments.
- Re-run the Responses/OpenCode focused test slice and ruff.
