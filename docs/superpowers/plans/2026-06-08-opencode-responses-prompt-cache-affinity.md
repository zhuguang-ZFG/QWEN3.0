# OpenCode Responses Prompt Cache Affinity Plan

**Goal:** Make OpenCode Responses `prompt_cache_key` participate in LiMa's
existing session-affinity routing.

## Problem

OpenCode can send `prompt_cache_key` as a session-level cache key. LiMa now
preserves it in shimmed Responses objects, but the converted internal chat
request does not use it for sticky routing. The routing engine already honors
`x-session-affinity`, so Responses requests are missing an existing integration
point.

## Design

- When `/v1/responses` receives a non-empty `prompt_cache_key`, synthesize
  `x-session-affinity` for the internal `handle_chat` call.
- Do not override a client-supplied `x-session-affinity` header.
- Keep this internal only; do not add provider-facing request fields.

## Verification

- Add endpoint tests for synthesized affinity and explicit-header precedence.
- Run the Responses/OpenCode focused test slice and ruff.
