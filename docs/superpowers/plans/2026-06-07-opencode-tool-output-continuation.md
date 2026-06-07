# OpenCode Tool Output Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix real OpenCode `/v1/responses` tool continuation so CLI tool calls can complete end-to-end through LiMa.

**Architecture:** Keep the production route unchanged. Extend `converters/responses_api.py` so OpenCode's standalone `function_call_output` continuation input becomes a non-empty chat turn, and fix request log SSE fan-out to import from `routes.admin_sse`.

**Tech Stack:** Python 3.10, FastAPI, OpenAI Responses API shim, OpenCode CLI 1.16.2, pytest, ruff, VPS systemd deploy.

---

### Task 1: Reproduce and Capture Root Cause

**Files:**
- Read: `converters/responses_api.py`
- Read: `routes/responses_endpoints.py`
- Read: `routes/request_tracking.py`
- Reference: `opencode-source/packages/llm/src/protocols/openai-responses.ts`

- [x] **Step 1: Run real OpenCode CLI tool E2E**

Run:
```powershell
$env:OPENAI_BASE_URL='https://chat.donglicao.com/v1'; $env:OPENAI_API_KEY=$env:LIMA_API_KEY; opencode run --model lima/lima-1.3 --format json --dangerously-skip-permissions "Use the read tool to read AGENTS.md in this repository. Then reply exactly two lines: first LIMA_OPENCODE_TOOL_E2E, second the first markdown heading you found."
```

Observed: first OpenCode step emitted a real `tool_use` for `read`, but the continuation call failed with `/v1/responses` `400 Empty query`.

### Task 2: Responses API Continuation Fix

**Files:**
- Modify: `converters/responses_api.py`
- Test: `tests/test_responses_api.py`

- [x] **Step 1: Add tests for standalone function_call_output**

Add tests that send:
```python
{
    "model": "lima-1.3",
    "input": [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "file contents",
        }
    ],
}
```

Expected: converted chat has a non-empty user message containing the call id and output.

- [x] **Step 2: Implement conversion**

Handle top-level Responses input items with `type == "function_call_output"` by producing a user continuation message. This keeps LiMa stateless and avoids invalid chat history when OpenCode references a previous response id instead of resending the assistant tool call.

- [x] **Step 3: Run tests**

Run:
```powershell
.venv310\Scripts\python.exe -m pytest tests\test_responses_api.py tests\test_responses_endpoints.py -q
```

Expected: pass.

Actual: `tests/test_responses_api.py`, `tests/test_responses_endpoints.py`,
and `tests/test_request_stats.py` passed. Added a second boundary test for
`function_call_output` nested inside a `content` list.

### Task 3: Request Tracking SSE Fan-Out Fix

**Files:**
- Modify: `routes/request_tracking.py`
- Test: `tests/test_request_stats.py`

- [x] **Step 1: Add/adjust test for admin SSE import**

Patch `routes.admin_sse.publish_log_event` and verify `record_request()` schedules it without warning.

- [x] **Step 2: Fix import**

Change `record_request()` to import `_main_sse_loop` and `publish_log_event` from `routes.admin_sse`, not `routes.admin_api`.

- [x] **Step 3: Run tests**

Run:
```powershell
.venv310\Scripts\python.exe -m pytest tests\test_request_stats.py -q
```

Expected: pass.

Actual: request stats tests passed and the fan-out warning no longer appears in
the post-deploy VPS log window.

### Task 4: Local Verification and Real OpenCode E2E

**Files:**
- Verify: OpenCode CLI
- Verify: VPS `/health`

- [x] **Step 1: Run focused OpenCode tests**

Run:
```powershell
$files = rg --files tests | Where-Object { $_ -match 'test_opencode_.*\.py$' }; .venv310\Scripts\python.exe -m pytest $files tests\test_responses_api.py tests\test_responses_endpoints.py -q
```

- [x] **Step 2: Deploy via unified script**

Run:
```powershell
.venv310\Scripts\python.exe scripts\deploy_unified.py --files converters/responses_api.py routes/request_tracking.py tests/test_responses_api.py tests/test_request_stats.py
```

- [x] **Step 3: Re-run real OpenCode CLI tool E2E**

Expected: OpenCode emits `tool_use`, submits tool output, receives final answer, and exits with code 0.

Actual final response:
```text
LIMA_OPENCODE_TOOL_E2E_FINAL
# AGENTS.md
```

- [x] **Step 4: Verify VPS logs**

Expected: `lima-router.service` active, `/health` OK, `/v1/responses` 200 OK, no new `Empty query`, no request tracking fan-out import warning.

Actual: `lima-router.service` active, `/health` OK, `/v1/responses` 200 OK.
Filtered logs after the final deploy showed no `Empty query`, no `Failed to
fan-out`, no `ReadTimeout`, and no ASGI exception.
