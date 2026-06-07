# OpenCode Responses Source Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align LiMa's `/v1/responses` shim with OpenCode's source-level OpenAI Responses request shapes.

**Architecture:** Keep `routes/responses_endpoints.py` unchanged and tighten conversion inside `converters/`. Move Responses content formatting into a focused helper module so the oversized adapter does not grow further.

**Tech Stack:** Python 3.10, OpenAI Responses API shim, OpenCode upstream `packages/llm/src/protocols/openai-responses.ts`, pytest, ruff.

---

### Task 1: Add OpenCode Source-Shape Regression Tests

**Files:**
- Modify: `tests/test_responses_api.py`
- Reference: `opencode-source/packages/llm/src/protocols/openai-responses.ts`

- [x] Add a regression test proving `reasoning` and `item_reference` input items do not become empty chat turns.
- [x] Add a regression test proving `function_call_output.output` arrays are converted into readable text/image markers.
- [x] Add a regression test proving Responses options `top_p`, `store`, `include`, and `previous_response_id` do not break chat conversion.

### Task 2: Implement Focused Content Conversion

**Files:**
- Create: `converters/responses_content.py`
- Modify: `converters/responses_api.py`

- [x] Move content-to-text and tool-output continuation formatting into `converters/responses_content.py`.
- [x] Skip OpenCode replay metadata items with `type == "reasoning"` or `type == "item_reference"`.
- [x] Preserve array tool outputs as newline-joined text, with image outputs represented as bounded markers.
- [x] Pass `top_p` through to the internal chat body when present.

### Task 3: Verify

**Files:**
- Test: `tests/test_responses_api.py`
- Test: `tests/test_responses_endpoints.py`

- [x] Run focused Responses tests.
- [x] Run ruff on touched files.
- [x] Report remaining risk and any tests not run.
