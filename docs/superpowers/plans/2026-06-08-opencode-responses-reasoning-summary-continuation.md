# OpenCode Responses Reasoning Summary Continuation Plan

**Goal:** Preserve useful OpenCode Responses continuation context when native
reasoning replay items are downgraded to Chat Completions.

## Problem

OpenCode native Responses continuation requests can include a `reasoning` input
item with `summary` text plus `encrypted_content`. LiMa currently drops the
whole item because Chat Completions backends cannot consume the native
`reasoning` shape. That also discards the visible summary text that could help
the fallback chat backend continue coherently.

## Design

- Convert `reasoning.summary` text into a plain assistant context message.
- Never include `encrypted_content` in chat messages.
- Continue dropping `item_reference` because it is an opaque provider-native
  reference that chat backends cannot resolve.

## Verification

- Add unit coverage for preserving summary text while excluding encrypted
  content.
- Re-run the Responses/OpenCode focused test slice and ruff.
