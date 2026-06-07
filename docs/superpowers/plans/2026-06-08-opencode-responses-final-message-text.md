# OpenCode Responses Final Message Text Plan

**Goal:** Make LiMa's OpenAI Responses streaming shim preserve assistant text in the final message item, not only in `response.output_text.delta` events.

## Source Research Summary

OpenCode's upstream `openai-responses.ts` parser consumes `response.output_text.delta` for live text and also validates Responses output items against an `output_text` content schema. LiMa already emits text deltas, but the final `response.output_item.done` message currently contains `{"type": "output_text", "text": ""}`. That is lossy for clients that reconcile or persist the completed output item.

## Scope

- Keep the existing Chat SSE to Responses SSE bridge.
- Accumulate assistant text chunks received from Chat `choices[].delta.content`.
- Emit the accumulated text in the final message `response.output_item.done`.
- Do not alter unrelated dirty work or delete files.

## Verification

- Add a focused regression test in `tests/test_responses_api.py`.
- Run the Responses/OpenCode focused pytest slice.
- Run ruff on touched Python files.
