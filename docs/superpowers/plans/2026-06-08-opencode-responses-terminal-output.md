# OpenCode Responses Terminal Output Plan

**Goal:** Make LiMa's Responses SSE terminal event include the completed output items that were already emitted during the stream.

## Problem

OpenCode's recorded native Responses streams finish with `response.completed.response.output` containing the completed reasoning, message, and function-call items. LiMa currently emits `response.output_item.done` events but leaves the terminal `response.output` array empty. Clients that reconcile state from the terminal response lose the final item list.

## Design

- Keep the existing stream event order.
- Build the same completed item payloads for `output_item.done` and terminal `response.output`.
- Include completed reasoning, message, and announced function-call items.
- Preserve incomplete terminal handling from the previous slice.

## Verification

- Add focused tests for terminal `response.output`.
- Run the Responses/OpenCode focused pytest slice.
- Run ruff on touched files.
