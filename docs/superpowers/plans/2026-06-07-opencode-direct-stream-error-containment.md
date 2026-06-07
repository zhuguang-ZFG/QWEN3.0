# OpenCode Direct Stream Error Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent OpenCode direct streaming backend failures from bubbling into ASGI exceptions.

**Architecture:** Keep the successful direct stream path unchanged. Add an error boundary around the direct stream generator: if the pinned backend fails before any SSE chunk is sent, fall back to the existing standard `stream_response()` path; if it fails after streaming has started, emit an OpenAI-compatible SSE error chunk and `[DONE]`.

**Tech Stack:** Python 3.10, FastAPI `StreamingResponse`, OpenAI SSE, pytest, real OpenCode CLI.

---

### Task 1: Add Regression Tests

**Files:**
- Modify: `tests/test_opencode_direct_stream.py`

- [x] **Step 1: Test pre-start fallback**

Create a fake `stream_openai_passthrough()` that raises `BackendError` before yielding. Patch `routes.chat_handler_dispatch.stream_response()` to yield a fallback chunk and `[DONE]`. Assert no exception escapes and fallback chunks are returned.

- [x] **Step 2: Test post-start error containment**

Create a fake `stream_openai_passthrough()` that yields one chunk, then raises `BackendError`. Assert no exception escapes, fallback is not called, an SSE error chunk is emitted, and the stream ends with `[DONE]`.

### Task 2: Implement Error Boundary

**Files:**
- Modify: `routes/chat_handler_dispatch.py`

- [ ] **Step 1: Add SSE error helper**

Add a small helper that converts `BackendError` status codes to OpenCode-parseable SSE errors: 429/503 map to `server_is_overloaded`, all other non-overflow failures map to `server_error`.

- [ ] **Step 2: Wrap direct stream generator**

Track whether any chunk has been yielded. On pre-start `BackendError`, log a warning and delegate to `stream_response()`. On post-start `BackendError`, log a warning, emit the error chunk, emit `[DONE]`, and return.

### Task 3: Verify and Deploy

**Files:**
- Deploy: `routes/chat_handler_dispatch.py`

- [ ] **Step 1: Run focused tests**

Run: `.venv310\Scripts\python.exe -m pytest tests\test_opencode_direct_stream.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run OpenCode suite slice**

Run: `$files = rg --files tests | Where-Object { $_ -match 'test_opencode_.*\.py$' }; .venv310\Scripts\python.exe -m pytest $files tests\test_responses_api.py tests\test_responses_endpoints.py tests\test_request_stats.py -q`

Expected: all selected tests pass.

- [ ] **Step 3: Deploy and real E2E**

Deploy `routes/chat_handler_dispatch.py`, run real OpenCode text and tool prompts, then inspect VPS logs for absence of new ASGI exceptions from the validation window.
