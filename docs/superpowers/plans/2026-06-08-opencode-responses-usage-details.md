# OpenCode Responses Usage Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve cache and reasoning token details when LiMa returns OpenAI Responses API payloads to OpenCode.

**Architecture:** Add a focused usage mapper under `converters/` and reuse it from non-streaming response conversion and streaming response completion events. Keep endpoint wiring unchanged.

**Tech Stack:** Python 3.10, OpenAI Responses usage schema, OpenCode upstream `openai-responses.ts`, pytest, ruff.

---

### Task 1: Add Usage Detail Regression Tests

**Files:**
- Modify: `tests/test_responses_api.py`

- [x] Add a non-streaming test for `prompt_tokens_details.cached_tokens`.
- [x] Add a non-streaming test for `completion_tokens_details.reasoning_tokens`.
- [x] Add a streaming test proving `response.completed.response.usage` contains the same details.

### Task 2: Implement Shared Usage Mapping

**Files:**
- Create: `converters/responses_usage.py`
- Modify: `converters/responses_api.py`
- Modify: `converters/responses_stream.py`

- [x] Map chat usage `prompt_tokens`/`completion_tokens`/`total_tokens` to Responses `input_tokens`/`output_tokens`/`total_tokens`.
- [x] Preserve `prompt_tokens_details.cached_tokens` as `input_tokens_details.cached_tokens`.
- [x] Preserve `completion_tokens_details.reasoning_tokens` as `output_tokens_details.reasoning_tokens`.
- [x] Reuse the same mapper in stream and non-stream paths.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run Responses tests.
- [x] Run OpenCode focused tests.
- [x] Run ruff on touched files.
