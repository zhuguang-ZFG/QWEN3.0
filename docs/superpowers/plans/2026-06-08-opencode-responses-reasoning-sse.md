# OpenCode Responses Reasoning SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve reasoning deltas when LiMa converts chat-completions SSE into OpenAI Responses SSE for OpenCode.

**Architecture:** Extend `ResponsesStreamConverter` so chat delta fields such as `reasoning_content` become the reasoning event sequence OpenCode's upstream parser consumes. Keep the endpoint and routing unchanged.

**Tech Stack:** Python 3.10, OpenAI Responses SSE, OpenCode upstream `packages/llm/src/protocols/openai-responses.ts`, pytest, ruff.

---

### Task 1: Add Reasoning SSE Regression Test

**Files:**
- Modify: `tests/test_responses_api.py`
- Reference: `opencode-source/packages/llm/src/protocols/openai-responses.ts`

- [x] Add a test with chat-completions SSE `delta.reasoning_content`.
- [x] Assert the converted stream emits `response.output_item.added` for a `reasoning` item.
- [x] Assert it emits `response.reasoning_summary_part.added`, `response.reasoning_summary_text.delta`, `response.reasoning_summary_part.done`, and a completed reasoning item.

### Task 2: Implement Reasoning Stream Mapping

**Files:**
- Modify: `converters/responses_api.py`
- Create: `converters/responses_stream.py`

- [x] Track a reasoning item id, output index, and accumulated summary text in `converters/responses_stream.py`.
- [x] Convert chat delta fields `reasoning_content`, `reasoning`, and `reasoning_text` into Responses reasoning summary events.
- [x] Allocate output indexes consistently across reasoning, message, and tool items.
- [x] Close active reasoning items in `completion_events()`.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run Responses tests.
- [x] Run OpenCode direct/E2E focused tests.
- [x] Run ruff on touched files.
