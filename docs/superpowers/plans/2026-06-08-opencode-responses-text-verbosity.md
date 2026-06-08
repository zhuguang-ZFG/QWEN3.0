# OpenCode Responses Text Verbosity Plan

**Goal:** Make OpenCode Responses `text.verbosity` affect downgraded Chat
Completions requests instead of only echoing it in response metadata.

## Problem

OpenCode's native Responses request builder can send `text: { verbosity:
"low" }` for GPT-5 class models. LiMa preserves that field in the shimmed
Responses object, but the converted Chat Completions request currently drops
its generation intent.

## Design

- Convert `text.verbosity` into a short system instruction before user input.
- Preserve any existing `instructions` field in the same system message.
- Keep accepted values constrained to `low`, `medium`, and `high`.

## Verification

- Add unit coverage for requests with and without existing `instructions`.
- Re-run the Responses/OpenCode focused test slice and ruff.
