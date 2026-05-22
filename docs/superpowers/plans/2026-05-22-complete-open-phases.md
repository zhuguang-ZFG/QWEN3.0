# Complete Open Personal Assistant Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining `task_plan.md` phases: IDE/agent verification, free web AI admission, and stability/free routing optimization.

**Architecture:** Treat "complete" as a verified operational decision, not as admitting every risky web page into production. Add a route-scoring module for quota/stability-aware backend ordering, generate a free web AI admission report from registry/probe evidence, and verify the public endpoint through both OpenAI-compatible and Anthropic/IDE-compatible flows.

**Tech Stack:** Python 3.10, existing LiMa router modules, pytest, PowerShell smoke commands, VPS `lima-router`.

---

## File Structure

| File | Responsibility |
|---|---|
| `route_scorer.py` | Small deterministic effective-score implementation for routing. |
| `routing_engine.py` | Use route scoring and block terminal auth/quota/manual-refresh states. |
| `budget_manager.py` | Expose remaining-quota score and test reset helpers. |
| `free_web_ai_admission.py` | Convert registry/probe evidence into sandbox/admitted/rejected decisions. |
| `scripts/build_free_web_ai_admission.py` | CLI that writes admission JSON and Markdown. |
| `tests/test_free_web_ai_admission.py` | Admission report tests. |
| `test_routing_engine.py` | Routing score and blocked-state regression tests. |
| `data/free_web_ai_candidates.json` | Updated candidate registry including newly found no-login pages. |
| `docs/FREE_WEB_AI_ADMISSION.md` | Human-readable admission decision record. |
| `data/free_web_ai_admission.json` | Machine-readable admission decision record. |
| `task_plan.md`, `STATUS.md`, `docs/LIMA_MEMORY.md`, `docs/DOCUMENTATION_STATUS.md` | Completion evidence. |

## Task 1: Free Web AI Admission

**Files:**
- Modify: `data/free_web_ai_candidates.json`
- Create: `free_web_ai_admission.py`
- Create: `scripts/build_free_web_ai_admission.py`
- Create: `tests/test_free_web_ai_admission.py`
- Create/Update: `docs/FREE_WEB_AI_ADMISSION.md`
- Create/Update: `data/free_web_ai_admission.json`

- [x] **Step 1: Add failing tests**

Tests must prove:

- DuckAI can be admitted only as a late local fallback when `reverse_status=already_reversed_local`, probe is `ok`, and local coding admission is recorded.
- Page-only no-login candidates remain `sandbox_only`, even when reachable.
- Private code is never allowed unless `private_code_allowed=true` and admission status is `admitted`.

- [x] **Step 2: Implement admission builder**

Expose exact signatures:

```python
def decide_candidate(candidate: dict, probe: dict | None) -> dict: ...
def build_admission(candidates: list[dict], probes: list[dict]) -> list[dict]: ...
def write_json(path: str | Path, decisions: list[dict]) -> None: ...
def write_markdown(path: str | Path, decisions: list[dict]) -> None: ...
```

Decisions:

- `admitted_late_fallback`: already-reversed local candidates with `admission_passed=true` and probe not blocked.
- `adapter_draft_pending`: candidates with an existing draft but no successful model smoke.
- `sandbox_only`: reachable page-only candidates.
- `rejected`: blocked/quota/auth candidates or candidates requiring bypass.

- [x] **Step 3: Update registry**

Keep DuckAI and HeckAI records. Add current page-only candidates found on 2026-05-22:

- `deep_seek_ai` -> `https://deep-seek.ai/`
- `glm_ai_chat` -> `https://glm-ai.chat/`
- `instantseek` -> `https://instantseek.org/`
- `chat_gpt_org` -> `https://chat-gpt.org/`

All new candidates must have `enabled=false` and `private_code_allowed=false`.

- [x] **Step 4: Generate evidence files**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20
D:\GIT\venv\Scripts\python.exe scripts\build_free_web_ai_admission.py
```

Expected: `data/free_web_ai_probe_results.json`, `data/free_web_ai_admission.json`, and `docs/FREE_WEB_AI_ADMISSION.md` are written.

## Task 2: Quota/Stability-Aware Routing

**Files:**
- Create: `route_scorer.py`
- Modify: `routing_engine.py`
- Modify: `budget_manager.py`
- Modify: `test_routing_engine.py`

- [x] **Step 1: Add scoring tests**

Tests must prove:

- A healthy high-quality free backend beats a lower-score fallback for simple chat.
- A `manual_refresh_required` backend is not selected.
- IDE/tool-call routes exclude unproven web adapters such as DuckAI.

- [x] **Step 2: Implement scoring**

Use:

```text
effective_score =
  quality_score * 0.45
  + stability_score * 0.25
  + latency_score * 0.15
  + remaining_quota_score * 0.10
  + task_fit_score * 0.05
```

Keep stable ordering as a tie-breaker so first-tier SCNet/GitHub/Cloudflare order is not churned when scores are equal.

- [x] **Step 3: Wire routing**

`routing_engine.select()` must:

- filter exhausted budget;
- filter cooled-down or terminal auth/quota/manual-refresh states;
- filter unproven web adapters for `ide`;
- rank candidates by effective score.

## Task 3: IDE/Agent Verification

**Files:**
- Create: `docs/IDE_AGENT_VERIFICATION.md`
- Update: `STATUS.md`, `docs/LIMA_MEMORY.md`, `task_plan.md`

- [x] **Step 1: Verify Anthropic IDE-compatible flow**

Run public `/v1/messages` smoke with a Claude Code style request and exact-output prompt.

- [x] **Step 2: Verify OpenAI-compatible IDE flow**

Run public `/v1/chat/completions` with IDE-like headers/system text and exact-output prompt.

- [x] **Step 3: Try real Claude Code CLI if available**

Run non-interactive `claude` only if the local CLI exposes a print/non-interactive mode. Record success or blocker; do not depend on interactive UI for automated completion.

## Task 4: Verification, Deploy, Docs, Git

**Files:**
- Update all touched docs.

- [x] **Step 1: Local verification**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m py_compile route_scorer.py free_web_ai_admission.py routing_engine.py budget_manager.py test_routing_engine.py tests\test_free_web_ai_admission.py
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py tests\test_coding_eval.py tests\test_lima_context.py tests\test_free_web_ai_probe.py tests\test_free_web_ai_admission.py -q --ignore=active_model
```

- [x] **Step 2: Deploy**

Back up `/opt/lima-router`, upload changed runtime Python files, compile remotely, restart `lima-router`, and verify `/health`.

- [x] **Step 3: Public smokes**

Verify:

- `/v1/chat/completions` exact `phase-complete-ok`.
- `/v1/messages` exact `ide-agent-complete`.
- `http://47.112.162.80:8088/health` status `ok`.

- [x] **Step 4: Commit and push**

Stage only related files, commit, and push the current branch.
