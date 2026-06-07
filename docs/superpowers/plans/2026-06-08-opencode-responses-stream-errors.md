# OpenCode Responses Stream Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert upstream chat-completions SSE errors into OpenAI Responses error semantics that OpenCode surfaces correctly.

**Architecture:** Keep route wiring unchanged. Extend `converters.responses_stream.ResponsesStreamConverter` so chat SSE `data: {"error": ...}` emits `response.failed` and terminates without a false `response.completed`.

**Tech Stack:** Python 3.10, OpenAI Responses SSE, OpenCode upstream `openai-responses.ts`, pytest, ruff.

---

### Task 1: Add Error Regression Test

**Files:**
- Modify: `tests/test_responses_api.py`

- [x] Add a test with chat-completions SSE `data: {"error": {"message": ..., "code": ..., "param": ...}}`.
- [x] Assert the converted stream emits `response.failed` with `response.error`.
- [x] Assert it does not emit `response.completed` after the failure.

### Task 2: Implement Failed Response Mapping

**Files:**
- Modify: `converters/responses_stream.py`
- Create: `converters/responses_errors.py`
- Create: `converters/responses_stream_transform.py`

- [x] Normalize chat error payloads into Responses error shape.
- [x] Emit `response.failed` with response id, status, model, usage, and error.
- [x] Stop sync and async stream conversion immediately after a failed response event.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run Responses tests.
- [x] Run OpenCode focused tests.
- [x] Run ruff on touched files.
