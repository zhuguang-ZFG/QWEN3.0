# Local Reverse AI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote already-reversed local/free web AI backends only after their current local state, request format, and failure handling are verified.

**Architecture:** Treat `docs/LOCAL_REVERSE_AI_STATUS.md` as the source-of-truth inventory. Fix the smallest integration blockers first: DuckAI request format and model coverage, then Kimi/OldLLM health states, then SCNet-large route-path evaluation. New web candidates remain sandbox-only until existing reverse assets are stable.

**Tech Stack:** Python 3.10, FastAPI LiMa router, `http_caller.py`, `backends.py`, pytest, Windows local proxies under `D:\ollama_server`, DuckAI Bun service under `D:\duckai`.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/LOCAL_REVERSE_AI_STATUS.md` | Durable inventory of what is already reversed, what is only proxied, and what remains page-only research. |
| `backends.py` | Backend registration, model IDs, provider-specific flags such as no-system-message handling. |
| `http_caller.py` | Request body construction and backend HTTP transport. |
| `test_http_caller.py` | Regression tests for provider-specific request body behavior. |
| `scripts/eval_coding_backends.py` | Reusable fixture runner for route-path admission checks. |
| `docs/free-web-ai-candidates.md` | Human-readable sandbox candidate status. |
| `docs/LIMA_MEMORY.md`, `STATUS.md`, `task_plan.md`, `findings.md`, `progress.md` | Project memory and current state records. |

## Task 1: DuckAI Request Format Fix

**Files:**
- Modify: `http_caller.py`
- Modify: `backends.py`
- Modify: `test_http_caller.py`
- Update: `docs/LOCAL_REVERSE_AI_STATUS.md`

- [ ] **Step 1: Write a failing test for OpenAI no-system backends**

Add a test that builds a body for an OpenAI backend with `no_system=True` and asserts the first message is the user message, not an empty system message.

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q test_http_caller.py
```

Expected before implementation: the new assertion fails because `_build_body` prepends `role=system`.

- [ ] **Step 2: Implement the `no_system` OpenAI branch**

Change `_build_body` so OpenAI-format backends with `backend_cfg.get("no_system")` omit the synthetic system message. If `system_prompt` or IDE context exists, prepend it to the first user message as text instead of using `role=system`.

- [ ] **Step 3: Mark DuckAI backends as no-system and add missing models**

In `backends.py`, set `no_system: True` for existing `ddg_*` backends and add:

```python
'ddg_gpt5_mini'
'ddg_claude_haiku_45'
'ddg_tinfoil_gptoss_120b'
```

Use models from local `/v1/models`: `gpt-5-mini`, `claude-haiku-4-5`, and `tinfoil/gpt-oss-120b`.

- [ ] **Step 4: Verify locally**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q test_http_caller.py test_routing_engine.py --ignore=active_model
curl.exe --noproxy "*" -sS --max-time 20 http://127.0.0.1:4500/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}]}"
```

Expected: tests pass; DuckAI local chat returns HTTP 200.

## Task 2: DuckAI Route Admission

**Files:**
- Modify: `router_v3.py`
- Modify: `code_orchestrator.py`
- Update: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Update: `docs/LOCAL_REVERSE_AI_STATUS.md`

- [ ] **Step 1: Keep DuckAI late until route-path fixture passes**

Add DuckAI models only to a late free fallback pool, not first-tier coding.

- [ ] **Step 2: Run a focused coding fixture through LiMa**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\eval_coding_backends.py --backends ddg_gpt4o_mini,ddg_gpt5_mini,ddg_claude_haiku_45,ddg_tinfoil_gptoss_120b --max-cases 3
```

Expected: record pass count, latency, and failure class. Do not promote any DuckAI model that fails formatting or times out.

- [ ] **Step 3: Update route decision docs**

Record exact winners and failures in `docs/LOCAL_REVERSE_AI_STATUS.md` and `docs/FREE_MODEL_ROUTING_STATUS.md`.

## Task 3: Kimi Session Refresh Gate

**Files:**
- Inspect: `D:\ollama_server\kimi_refresh.js`
- Inspect: `D:\ollama_server\kimi_session.json`
- Modify if needed: `health_tracker.py`
- Update: `docs/LOCAL_REVERSE_AI_STATUS.md`

- [ ] **Step 1: Confirm current failure class**

Run:

```powershell
curl.exe --noproxy "*" -sS --max-time 35 http://127.0.0.1:4504/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"kimi\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}]}"
```

Expected current failure: `chat.anonymous_usage_exceeded`.

- [ ] **Step 2: Refresh session only if the local browser/login state is available**

Run the existing refresh script manually, then repeat the chat smoke. If manual login is required, document that state and keep Kimi inactive.

- [ ] **Step 3: Keep failed Kimi out of hot-path retries**

Verify `health_tracker` classifies the failure as `manual_refresh_required` or `quota_exhausted`.

## Task 4: SCNet-Large Route-Path Evaluation

**Files:**
- Use: `scripts/eval_coding_backends.py`
- Update: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Update: `docs/LOCAL_REVERSE_AI_STATUS.md`

- [ ] **Step 1: Verify local proxy still passes**

Run:

```powershell
curl.exe --noproxy "*" -sS --max-time 35 http://127.0.0.1:4505/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"deepseek-v4-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}]}"
```

Expected: HTTP 200 OpenAI-compatible response.

- [ ] **Step 2: Evaluate through LiMa route path**

Run the coding fixture against `scnet_large_ds_flash` and `scnet_large_ds_pro` through the Windows LiMa router or public FRP path.

- [ ] **Step 3: Decide promotion**

Promote only if route-path fixture quality and latency beat current direct SCNet first-tier models.

## Task 5: TheOldLLM Timeout Diagnosis

**Files:**
- Inspect: `D:\ollama_server\oldllm_proxy.js`
- Inspect: `D:\ollama_server\oldllm_proxy.log`
- Inspect: `D:\ollama_server\token_refresh_server.js`
- Update: `docs/LOCAL_REVERSE_AI_STATUS.md`

- [ ] **Step 1: Reproduce timeout**

Run local `4502` chat with a 30 second timeout and record whether it times out, returns auth failure, or returns content.

- [ ] **Step 2: Check refresh helper**

Confirm whether the refresh helper can obtain a current token without exposing token values in logs or docs.

- [ ] **Step 3: Keep oldllm late**

Do not place TheOldLLM in coding hot path until local chat and public worker chat both pass.

## Task 6: Candidate Backlog Cleanup

**Files:**
- Modify: `docs/free-web-ai-candidates.md`
- Modify: `data/free_web_ai_candidates.json`
- Update: `docs/FREE_WEB_AI_EXPANSION_PLAN.md`

- [ ] **Step 1: Remove DuckAI from net-new research**

Keep DuckAI in the registry only as `already_reversed_local`; do not spend new reverse-engineering time on it.

- [ ] **Step 2: Promote HeckAI from page-only to adapter-draft**

Record that `D:\ollama_server\heckai-worker.js` exists and must be smoked before any new capture work.

- [ ] **Step 3: Keep HIX/GPT.chat/Deep-seek/PLAI page-only**

Do not build adapters until Task 1-5 are closed.
