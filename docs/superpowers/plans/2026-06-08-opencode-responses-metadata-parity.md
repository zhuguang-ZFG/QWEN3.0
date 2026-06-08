# OpenCode Responses Metadata Parity Plan

**Goal:** Preserve OpenCode's native Responses request metadata in shimmed
Responses objects without changing backend routing behavior.

## Problem

OpenCode's native Responses path sends fields such as `store`,
`prompt_cache_key`, `include`, `reasoning.summary`, and `text.verbosity`.
LiMa currently converts the request to Chat Completions and emits minimal
Responses objects, so those fields disappear from `response.created`,
`response.in_progress`, and terminal response events.

## Design

- Extract response-object request fields from the original `/v1/responses`
  body, excluding payload-only fields such as `input` and `stream`.
- Merge those fields into non-stream and stream Responses objects.
- Keep backend calls unchanged; these fields are response-shape metadata here,
  not forced Chat Completions passthrough.
- Move stream parsing helpers out of `responses_stream.py` so the file remains
  under the 300-line target while adding behavior.

## Verification

- Add focused unit coverage for non-stream and stream metadata preservation.
- Run Responses/OpenCode focused tests and ruff on touched files.
