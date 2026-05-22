# IDE Context Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve LiMa coding-agent experience by adding a lightweight request context preflight layer inspired by Cursor, Claude Code, and Codex CLI.

**Architecture:** Keep the first version server-side and low risk. LiMa cannot directly read a user's local IDE workspace from the VPS, so the preflight layer extracts only context already present in the request: IDE source, system prompt hints, file paths, tool results, errors, language signals, and task shape. The digest is injected as a short system block before routing so coding backends spend fewer turns rediscovering context.

**Tech Stack:** Python standard library, existing `server.py`, existing `code_orchestrator.py`, pytest, current VPS deployment flow.

---

## Source Research Summary

The three deep-dive documents point to one shared lesson: better coding experience comes from context engineering more than prompt size.

| Tool | Useful lesson | LiMa adaptation |
|---|---|---|
| Cursor Auto | Minimal system prompt plus silent context injection beats huge instruction blocks. | Add compact request-local context digest before backend routing. |
| Claude Code | Planning files and tool-rich workflows make long tasks resilient. | Keep `task_plan.md`, `findings.md`, and `progress.md`; improve `/v1/messages` tool path. |
| Codex CLI | Goals/thread tracking helps long-running coding sessions survive context churn. | Future phase: persist per-task goal state; do not build this before context preflight works. |

## File Structure

| File | Responsibility |
|---|---|
| `lima_context.py` | Build a short context digest from request messages/system prompt without touching local user files. |
| `tests/test_lima_context.py` | Unit tests for path extraction, error detection, tool-result summarization, and digest limits. |
| `code_orchestrator.py` | Inject digest into normal coding route system prompt. |
| `server.py` | Inject digest into Anthropic `/v1/messages` tool-call route before forwarding to OpenAI-compatible backends. |
| `test_routing_engine.py` | Regression tests for integration behavior where practical. |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | Document the context preflight direction. |
| `task_plan.md`, `findings.md`, `progress.md` | Persistent execution record. |

## Task 1: Context Preflight Core

**Files:**
- Create: `lima_context.py`
- Create: `tests/test_lima_context.py`

- [x] **Step 1: Write tests for digest extraction**

Run: `python -m pytest -q tests/test_lima_context.py`
Expected before implementation: import failure for `lima_context`.

- [x] **Step 2: Implement `build_context_digest`**

Required signature:

```python
def build_context_digest(
    query: str,
    messages: list[dict],
    *,
    system_prompt: str = "",
    ide_source: str = "",
    max_chars: int = 1600,
) -> str:
    ...
```

The function must:

- Return `""` when there is no useful context beyond a trivial query.
- Detect likely IDE source.
- Detect language from code/path/error signals.
- Extract up to 8 file paths from request text.
- Extract up to 6 error/tool signals.
- Keep output under `max_chars`.
- Include a boundary label: `LiMa context preflight`.
- Avoid claiming access to local user files on the VPS.

- [x] **Step 3: Verify core tests**

Run: `python -m pytest -q tests/test_lima_context.py`
Expected: all tests pass.

## Task 2: Normal Coding Route Injection

**Files:**
- Modify: `code_orchestrator.py`
- Test: `tests/test_lima_context.py` or `test_routing_engine.py`

- [x] **Step 1: Add digest to `enhance_context`**

Append the digest to the language guide system prompt only for `scenario == "coding"`.

- [x] **Step 2: Add regression test**

Verify `code_orchestrator.enhance_context(...)["system_prompt"]` contains `LiMa context preflight` for a coding request with file/error context.

- [x] **Step 3: Run tests**

Run: `python -m pytest -q tests/test_lima_context.py test_routing_engine.py`
Expected: pass.

## Task 3: Anthropic Tool Route Injection

**Files:**
- Modify: `server.py`
- Test: `test_routing_engine.py`

- [x] **Step 1: Add digest to `_anthropic_native_forward_sync` and `_anthropic_native_stream`**

When converting Anthropic messages to OpenAI messages, include the digest in the first system message. If an existing system prompt exists, append the digest separated by a blank line.

- [x] **Step 2: Keep fast tool backend behavior**

Do not undo the fast `TOOL_TIER1_BACKENDS` ordering or distinct-backend retry behavior.

- [x] **Step 3: Run tests**

Run: `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py`
Expected: pass.

## Task 4: Deploy And Smoke

**Files:**
- Deploy: `server.py`, `code_orchestrator.py`, `lima_context.py`

- [x] **Step 1: Remote backup and upload**

Backup changed files under `/opt/lima-router/backups/context-preflight-<timestamp>/`, upload only the changed runtime files.

- [x] **Step 2: Remote compile and restart**

Run: `cd /opt/lima-router && /usr/local/bin/python3.10 -m py_compile server.py code_orchestrator.py lima_context.py`
Expected: exit code 0.

Restart: `systemctl restart lima-router`

- [x] **Step 3: Smoke tests**

Run VPS-local `/health`.
Run public Anthropic `/v1/messages` with a request containing a file path, error text, and tool schema.
Expected: 200 response and no regression in tool_use behavior.

## Task 5: Documentation Closure

**Files:**
- Modify: `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [x] **Step 1: Record the implemented behavior**

Document that the first Cursor-inspired feature is request-local context preflight, not full workspace indexing.

- [x] **Step 2: Record verification evidence**

Include local test output and VPS smoke results.

---

## Self-Review

- Spec coverage: This plan turns the three deep-dive documents into one concrete first feature and leaves larger goals/thread persistence for later.
- Placeholder scan: No `TBD` or unspecified implementation steps remain.
- Type consistency: The only new public function is `build_context_digest(...) -> str`, used by both `code_orchestrator.py` and `server.py`.

## Closure Evidence

- Local compile: `python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py` exited 0.
- Local tests: `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py` returned `70 passed in 0.51s`.
- VPS backup: `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Final encoding-sync backup: `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- VPS compile: `server.py code_orchestrator.py lima_context.py` compiled with `/usr/local/bin/python3.10`.
- VPS local health: `http://127.0.0.1:8080/health` returned 200.
- Final public Anthropic tool smoke: `https://chat.donglicao.com/v1/messages` returned 200 in 600ms with `stop_reason=tool_use`.
