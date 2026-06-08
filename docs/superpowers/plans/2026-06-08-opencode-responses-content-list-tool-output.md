# OpenCode Responses Content-List Tool Output Plan

**Goal:** Avoid invalid Chat Completions `tool` messages when downgrading
Responses content-list `function_call_output` parts.

## Problem

`_convert_content_list()` can emit `role: "tool"` messages with
`tool_call_id`, but `ChatRequest.Message` does not preserve `tool_call_id`.
After Pydantic parsing, those can become malformed tool messages. Top-level
Responses `function_call_output` is already downgraded to a user-readable
continuation prompt; content-list outputs should follow the same safe path.

## Design

- Convert content-list `function_call_output` parts to continuation text.
- Preserve nearby text parts in the same message.
- Keep `function_call` parts as assistant tool call messages.

## Verification

- Add coverage for mixed text plus `function_call_output` content.
- Re-run the Responses/OpenCode focused test slice and ruff.
