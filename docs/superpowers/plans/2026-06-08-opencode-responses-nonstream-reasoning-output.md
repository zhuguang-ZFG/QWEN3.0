# OpenCode Responses Non-Stream Reasoning Output Plan

**Goal:** Preserve non-stream Chat Completions reasoning content in shimmed
OpenCode Responses output.

## Problem

The streaming Responses converter maps `delta.reasoning_content` into
Responses reasoning summary events. The non-stream converter only emits message
text and function calls, so a backend response with `message.reasoning_content`
loses its reasoning output.

## Design

- Detect non-stream assistant reasoning fields before normal message content.
- Emit a completed Responses `reasoning` output item using the existing item
  builder.
- Keep `encrypted_content` as `None`; chat backends do not return native
  encrypted reasoning state.

## Verification

- Add focused non-stream reasoning output coverage.
- Re-run the Responses/OpenCode focused test slice and ruff.
