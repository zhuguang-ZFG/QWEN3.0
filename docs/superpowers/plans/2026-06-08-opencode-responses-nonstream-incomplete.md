# OpenCode Responses Non-Stream Incomplete Plan

**Goal:** Align non-stream `/v1/responses` status handling with the existing
streaming incomplete mapping.

## Problem

The stream converter maps Chat Completions `finish_reason="length"` to
Responses `status="incomplete"` with `incomplete_details.reason` set to
`max_output_tokens`. The non-stream converter still always returns
`status="completed"`, which hides max-token truncation from OpenCode.

## Design

- Reuse the existing Responses finish-reason mapping.
- Keep partial output in `response.output`.
- Mark only mapped reasons as incomplete; all other finish reasons remain
  completed.

## Verification

- Add focused non-stream tests for `length` and `content_filter`.
- Run the Responses/OpenCode focused pytest slice and ruff.
