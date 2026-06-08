# OpenCode Responses Non-Stream Direct Tools Plan

**Goal:** Keep `/v1/responses` OpenCode tool routing consistent with
`LIMA_OPENCODE_TOOL_MODE=direct` for both streaming and non-streaming requests.

## Problem

The Responses endpoint currently lets OpenCode tool requests fall through to
the direct OpenAI-format chat path only when `stream=true`. Non-stream OpenCode
tool requests still use the Anthropic conversion path, which diverges from the
chat completions endpoint and the default direct tool mode.

## Design

- Treat `has_tools && ide_source == "OpenCode" && OPENCODE_TOOL_MODE ==
  "direct"` as the direct path regardless of `stream`.
- Keep existing Anthropic conversion behavior for non-OpenCode clients and for
  explicit non-direct tool mode.

## Verification

- Add endpoint coverage proving non-stream OpenCode Responses tools reach
  `handle_chat`.
- Re-run the Responses/OpenCode focused test slice and ruff.
