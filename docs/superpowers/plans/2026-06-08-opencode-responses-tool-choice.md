# OpenCode Responses Tool Choice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert OpenCode/OpenAI Responses tool schemas and tool choices into Chat Completions-compatible shapes without dropping strict schema mode.

**Architecture:** Move Responses tool conversion into a focused converter module. Keep `/v1/responses` route wiring unchanged and update `responses_body_to_chat()` to use the shared helpers.

**Tech Stack:** Python 3.10, OpenAI Responses API, OpenAI Chat Completions tool schema, OpenCode upstream `openai-responses.ts`, pytest, ruff.

---

### Task 1: Add Tool Conversion Regression Tests

**Files:**
- Modify: `tests/test_responses_api.py`

- [x] Add a test proving Responses `tool_choice: {"type": "function", "name": "read"}` becomes Chat `{"type": "function", "function": {"name": "read"}}`.
- [x] Add a test proving string choices such as `required`, `auto`, and `none` pass through unchanged.
- [x] Add a test proving Responses tool `strict` is preserved under the Chat function schema.

### Task 2: Implement Shared Tool Conversion

**Files:**
- Create: `converters/responses_tools.py`
- Modify: `converters/responses_api.py`

- [x] Move `_convert_tools()` logic into `responses_tools.py`.
- [x] Preserve top-level Responses `strict` as `function.strict`.
- [x] Convert Responses function tool choice object into Chat Completions tool choice object.
- [x] Leave already Chat-shaped tool schemas and choices unchanged.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run Responses tests.
- [x] Run OpenCode focused tests.
- [x] Run ruff on touched files.
