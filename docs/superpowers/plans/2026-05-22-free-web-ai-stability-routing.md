# Free Web AI Stability Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add more no-login web AI capacity while improving backend stability and routing efficiency for free models.

**Architecture:** Keep new web AI sources behind a sandbox registry and probe harness first. Feed only normalized health/quota/auth signals into the existing LiMa router, then add quota-aware scoring after probes prove stable.

**Tech Stack:** Python 3.10, FastAPI runtime already in `server.py`, existing `routing_engine.py`, `router_v3.py`, `health_tracker.py`, `probe_loop.py`, pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/free-web-ai-candidates.md` | Human-readable candidate table and validation notes. |
| `data/free_web_ai_candidates.json` | Machine-readable candidate registry. |
| `scripts/probe_free_web_ai.py` | Harmless sandbox probe runner for no-login candidates. |
| `tests/test_free_web_ai_probe.py` | Unit tests for response/error normalization. |
| `health_tracker.py` | Backend state, cooldown, auth/quota/manual-refresh flags. |
| `probe_loop.py` | Slow probing of inactive backends without burning free quota. |
| `routing_engine.py` | Task-fit and quota-aware route scoring integration. |
| `router_v3.py` | Pool ordering and provider admission gates. |
| `budget_manager.py` | Remaining quota and free-capacity signals. |
| `STATUS.md`, `docs/LIMA_MEMORY.md` | Final verification and durable memory. |

## Task 1: Candidate Registry

**Files:**
- Create: `docs/free-web-ai-candidates.md`
- Create: `data/free_web_ai_candidates.json`

- [x] **Step 1: Write candidate registry docs**

Create `docs/free-web-ai-candidates.md` with this table structure:

```markdown
# Free Web AI Candidates

> Updated: 2026-05-22

| ID | URL | Access | Trust | Current State | Next Check |
|---|---|---|---|---|---|
| duck_ai | https://duck.ai/chat | no-login web | medium-high | research | capture harmless request flow |
| heck_ai | https://heck.ai/zh | no-login web | medium | research | capture harmless request flow |
| hix_chat | https://hix.ai/a/chat | no-login web | low-medium | research | check limits and data policy |
| gpt_chat | https://gpt.chat | no-login web | low | research | harmless probe only |
| deep_seek_mirror | https://deep-seek.com | no-login web | low | research | verify provenance |
| plai_chat | https://plai.chat | no-login web | low-medium | research | inspect model list and limits |
```

- [x] **Step 2: Write JSON registry**

Create `data/free_web_ai_candidates.json`:

```json
[
  {"id":"duck_ai","url":"https://duck.ai/chat","trust":"medium-high","enabled":false,"private_code_allowed":false},
  {"id":"heck_ai","url":"https://heck.ai/zh","trust":"medium","enabled":false,"private_code_allowed":false},
  {"id":"hix_chat","url":"https://hix.ai/a/chat","trust":"low-medium","enabled":false,"private_code_allowed":false},
  {"id":"gpt_chat","url":"https://gpt.chat","trust":"low","enabled":false,"private_code_allowed":false},
  {"id":"deep_seek_mirror","url":"https://deep-seek.com","trust":"low","enabled":false,"private_code_allowed":false},
  {"id":"plai_chat","url":"https://plai.chat","trust":"low-medium","enabled":false,"private_code_allowed":false}
]
```

- [x] **Step 3: Verify JSON loads**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m json.tool data\free_web_ai_candidates.json
```

Expected: pretty-printed JSON and exit code 0.

## Task 2: Sandbox Probe Harness

**Files:**
- Create: `scripts/probe_free_web_ai.py`
- Create: `tests/test_free_web_ai_probe.py`

- [x] **Step 1: Write tests for error normalization**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q tests\test_free_web_ai_probe.py
```

Expected before implementation: import failure for `scripts.probe_free_web_ai`.

- [x] **Step 2: Implement harmless probe CLI**

Required signatures:

```python
def normalize_error(status_code: int | None, text: str) -> str: ...
def load_candidates(path: str) -> list[dict]: ...
def write_results(path: str, results: list[dict]) -> None: ...
```

Probe prompt:

```text
Say OK only.
```

- [x] **Step 3: Verify probe tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q tests\test_free_web_ai_probe.py
```

Expected: all tests pass.

## Task 3: Stability State

**Files:**
- Modify: `health_tracker.py`
- Modify: `probe_loop.py`
- Modify: `test_routing_engine.py`

- [x] **Step 1: Add tests for quota/auth state**

Add cases for:

```text
chat.anonymous_usage_exceeded -> manual_refresh_required
HTTP 429 -> rate_limited
401/403 -> auth_expired
timeout -> cooldown
```

- [x] **Step 2: Implement state mapping**

Add backend state fields:

```text
state: ok | rate_limited | quota_exhausted | auth_expired | manual_refresh_required | timeout | provider_error
cooldown_until: unix timestamp
last_error_class: string
```

- [x] **Step 3: Verify routing tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q test_routing_engine.py
```

Expected: all tests pass.

## Task 4: Quota-Aware Routing

**Files:**
- Modify: `routing_engine.py`
- Modify: `router_v3.py`
- Modify: `budget_manager.py`

- [ ] **Step 1: Add scoring tests**

Add tests proving:

```text
healthy high-quality free backend beats slow paid fallback for simple task
manual_refresh_required backend is skipped
tool-call route excludes unproven web adapters
```

- [ ] **Step 2: Implement effective score**

Use this formula:

```text
effective_score =
  quality_score * 0.45
  + stability_score * 0.25
  + latency_score * 0.15
  + remaining_quota_score * 0.10
  + task_fit_score * 0.05
```

- [ ] **Step 3: Verify focused tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q test_routing_engine.py test_rate_limiter.py
```

Expected: all tests pass.

## Task 5: Closed-Loop Verification And Docs

**Files:**
- Update: `STATUS.md`
- Update: `docs/LIMA_MEMORY.md`
- Update: `docs/FREE_MODEL_ROUTING_STATUS.md`
- Update: `docs/free-web-ai-candidates.md`

- [ ] **Step 1: Run local verification**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
```

Expected: all tests pass.

- [ ] **Step 2: Run public FRP smoke**

Run:

```powershell
curl.exe --noproxy "*" -sS --max-time 15 http://47.112.162.80:8088/health
```

Expected: response contains `"status":"ok"`.

- [ ] **Step 3: Update memory docs**

Record:

```text
new candidates found
which probes passed
which candidates remain sandboxed
cooldown/quota behavior
route policy changes
verification command outputs
```

- [ ] **Step 4: Commit and push**

Run:

```powershell
git add STATUS.md docs data scripts tests health_tracker.py probe_loop.py routing_engine.py router_v3.py budget_manager.py test_routing_engine.py
git commit -m "feat: add free web AI stability routing"
git push origin master
```

Expected: push succeeds.
