# OpenCode Direct Stream Session Headers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve OpenCode session, request, and compaction headers on the direct streaming tool path.

**Architecture:** `start_chat_run()` already stores request headers in `ChatRunContext`, and `routes.opencode_direct_stream.stream_openai_passthrough()` already accepts and parses them. The missing link is the dispatch layer: `build_streaming_response()` must pass `ctx.request_headers` into the direct OpenCode stream call.

**Tech Stack:** Python 3.10, FastAPI `StreamingResponse`, pytest, OpenCode CLI real E2E.

---

### Task 1: Add Dispatch Regression Test

**Files:**
- Modify: `tests/test_opencode_direct_stream.py`

- [x] **Step 1: Write the failing test**

Add an async test that constructs a `ChatRunContext` with OpenCode headers, triggers the direct stream branch, consumes the response iterator, and asserts the fake `stream_openai_passthrough()` received `request_headers`.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv310\Scripts\python.exe -m pytest tests\test_opencode_direct_stream.py::test_build_streaming_response_passes_opencode_headers_to_direct_stream -q`

Expected before implementation: assertion failure because `request_headers` is missing or `None`.

### Task 2: Wire Request Headers

**Files:**
- Modify: `routes/chat_handler_dispatch.py`

- [x] **Step 1: Implement minimal dispatch fix**

Pass `request_headers=ctx.request_headers` to `stream_openai_passthrough()` in the OpenCode direct stream branch.

- [x] **Step 2: Run focused validation**

Run: `.venv310\Scripts\python.exe -m pytest tests\test_opencode_direct_stream.py::test_build_streaming_response_passes_opencode_headers_to_direct_stream -q`

Expected: `1 passed`.

### Task 3: Verify and Deploy

**Files:**
- Deploy: `routes/chat_handler_dispatch.py`

- [x] **Step 1: Run local suite slice**

Run: `.venv310\Scripts\python.exe -m pytest tests\test_opencode_direct_stream.py tests\test_opencode_request_headers.py -q`

Expected: all selected tests pass.

- [ ] **Step 2: Deploy to VPS**

Run: `.venv310\Scripts\python.exe scripts\deploy_unified.py --files routes/chat_handler_dispatch.py`

Expected: deployment completes and `lima-router.service` restarts.

- [ ] **Step 3: Real OpenCode E2E**

Run OpenCode CLI against `https://chat.donglicao.com/v1` with the LiMa API key and a real tool-use prompt.

Expected: OpenCode executes a local tool, sends the continuation, and receives a final answer from LiMa.
