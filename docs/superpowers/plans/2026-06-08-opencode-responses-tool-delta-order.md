# OpenCode Responses Tool Delta Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chat SSE tool-call delta conversion robust when argument chunks arrive before the tool name.

**Architecture:** Keep the Responses stream state machine authoritative for tool item ordering. Suppress argument delta events until the corresponding `response.output_item.added` has been emitted, while preserving accumulated arguments for the final `response.output_item.done`.

**Tech Stack:** Python 3.10, OpenAI Chat Completions SSE, OpenAI Responses SSE, OpenCode upstream `ToolStream`, pytest, ruff.

---

### Task 1: Add Tool Delta Order Regression Test

**Files:**
- Modify: `tests/test_responses_api.py`

- [x] Add a stream conversion test where a tool argument delta arrives before the tool name.
- [x] Assert the converted stream never emits `"output_index": null`.
- [x] Assert the final `function_call` item still contains the full accumulated arguments.

### Task 2: Implement Ordering Guard

**Files:**
- Modify: `converters/responses_stream.py`

- [x] Emit `response.function_call_arguments.delta` only after the tool item has been announced.
- [x] Emit `response.output_item.done` only for announced tool items.
- [x] Keep accumulating all argument chunks regardless of announcement timing.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run Responses tests.
- [x] Run OpenCode focused tests.
- [x] Run ruff on touched files.
