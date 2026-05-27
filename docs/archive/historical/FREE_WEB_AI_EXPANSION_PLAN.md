# Free Web AI Expansion Plan

> Date: 2026-05-22
> Status: Complete
> Scope: no-login or low-friction web AI sources, backend stability, and free-backend routing efficiency.

## Goal

Find more free web AI capacity without making LiMa fragile. New sources must enter through a sandbox adapter, pass repeatable coding/chat fixtures, and prove stable before they affect the main IDE route.

## Research Baseline

Current references checked on 2026-05-22:

| Source | Evidence | LiMa Decision |
|---|---|---|
| Duck.ai / DuckDuckGo AI Chat | `https://duck.ai/chat` returns 200; local `D:\duckai` already implements DuckAI OpenAI-compatible reverse bridge on `4500`. | Not net-new research. Fix LiMa request format, model registration, and public tunnel before routing. |
| HeckAI | `https://heck.ai/zh` returns 200 and `D:\ollama_server\heckai-worker.js` already contains a worker draft targeting HeckAI's upstream. | Adapter draft exists. Smoke the draft before new browser capture. |
| HIX Chat | Search result/page advertises free no-login AI chat with web access. | Candidate only; likely product-marketing surface, validate limits carefully. |
| GPT.chat / ChatGPTFree-style sites | Multiple sites advertise no-login ChatGPT-like access. | Low-trust candidate class. Only harmless probes; never send private code until provenance and retention are known. |
| Deep-seek.com | Search result/page advertises free AI chat with no signup/no limits. | Candidate only; name can be confused with official DeepSeek, so treat as untrusted mirror until verified. |
| PLAI.chat | Search result/page advertises 300+ models and no-login chat. | Candidate only; inspect protocol and data path before use. |
| `decolua/9router` | GitHub API reported 13,400 stars and active update on 2026-05-22; README emphasizes 40+ providers, quota tracking, auto token refresh, auto fallback, and token compression. | Study architecture, not drop-in replacement. Useful patterns: account/provider pools, quotas, failover, token compression. |
| `diegosouzapw/OmniRoute` | GitHub API reported 5,135 stars and active update on 2026-05-22; README emphasizes 160+ providers, free-provider routing, token compression, auto-fallback, circuit breakers, and rate-limit management. | Study architecture, not drop-in replacement. Useful patterns: unified OpenAI-compatible entry, health scoring, provider fallback. |
| `mrgick/duck_chat` | GitHub API reported 103 stars and active update on 2026-05-20; README says it is a Python DuckDuckGo AI chat client with model selection and dialog history. | Lightweight Duck.ai reference; inspect before writing a Duck adapter. |

Web candidates still need stricter validation before implementation:

| Candidate | Why It Is Interesting | Risk |
|---|---|---|
| Duck.ai | Already local, exposes six models, credible privacy posture. | LiMa currently sends a `system` message that DuckAI rejects; public tunnel currently returns 1033. |
| HeckAI | Existing worker draft can shorten integration. | Unknown limits, anti-bot behavior, and response stability. |
| Blackbox AI | Coding-focused web AI surface. | Login/rate limits may vary; higher ToS and anti-bot risk. |
| You.com / Perplexity-style answer engines | Search-grounded answers can help research/code questions. | Often optimized for search answers, not deterministic coding; API may require auth. |
| Other no-signup chat mirrors | Adds cheap fallback capacity if stable. | High breakage and abuse risk; never route private code until vetted. |

## Source Links

- Duck.ai: `https://duck.ai/chat`
- Duck.ai privacy/help: `https://duckduckgo.com/duckduckgo-help-pages/duckai/ai-chat-privacy`
- Duck.ai privacy terms: `https://duckduckgo.com/duckai/privacy-terms`
- HeckAI Chinese page: `https://heck.ai/zh`
- HeckAI free AI page: `https://heck.ai/intelligence-artificielle-gratuite`
- HIX Chat: `https://hix.ai/a/chat`
- GPT.chat: `https://gpt.chat`
- Deep-seek.com: `https://deep-seek.com`
- PLAI.chat: `https://plai.chat`
- 9Router: `https://github.com/decolua/9router`
- OmniRoute: `https://github.com/diegosouzapw/OmniRoute`
- Duck Chat reference: `https://github.com/mrgick/duck_chat`

## Admission Rules

A candidate can move from research to sandbox only if all checks pass:

1. Public access works without personal credentials.
2. Request protocol can be implemented without browser automation in the hot path.
3. It returns an answer for a harmless text prompt under 30 seconds.
4. It has detectable rate-limit or quota errors.
5. It does not require bypassing CAPTCHA, paywalls, or access controls.
6. It can be isolated from private code until trust is proven.

A candidate can move from sandbox to LiMa fallback only if all checks pass:

1. It passes at least 2/3 coding fixtures or is explicitly chat/research-only.
2. It returns parseable OpenAI-compatible content through the adapter.
3. It survives 20 sequential smoke calls without a high hard-failure rate.
4. Its failure modes map to `rate_limited`, `quota_exhausted`, `auth_expired`, `timeout`, or `provider_error`.
5. It has provider-specific cooldown and does not retry in a tight loop.

## Stability Work

Token/session refresh and rate limiting should be handled before adding many more sources.

| Area | Required Behavior |
|---|---|
| Token/session state | Track `ok`, `auth_expired`, `anonymous_quota_exceeded`, `captcha_required`, and `manual_refresh_required` per backend. |
| Kimi local proxy | Detect `chat.anonymous_usage_exceeded` and mark local Kimi as manual refresh required instead of repeatedly retrying it. |
| HTTP 429 | Apply provider-specific cooldown with exponential backoff and jitter. |
| Daily quotas | Store lightweight per-backend counters so free quota is preserved for coding requests. |
| Error normalization | Map provider-specific messages into stable LiMa error classes for routing decisions. |
| Probe loop | Probe inactive backends slowly; do not let health probes consume scarce daily free quota. |

## Routing Optimization

Free backends should be used by task value, not only static order.

| Route Need | Policy |
|---|---|
| Simple coding/edit/explain | Prefer fastest currently healthy free coder with acceptable score. |
| Multi-step bugfix or architecture | Prefer first-tier SCNet/GitHub/strong coder; avoid fragile web mirrors. |
| Chat/research | Use slower free web candidates when coding-quality constraints are low. |
| Tool-call/Claude Code | Prefer low-latency tool-safe backends; avoid web adapters until tool formatting is proven. |
| Repeated backend failure | Escalate tier and cool down the failed backend; do not retry the same backend in the same request. |

Recommended scoring formula for the next implementation:

```text
effective_score =
  quality_score * 0.45
  + stability_score * 0.25
  + latency_score * 0.15
  + remaining_quota_score * 0.10
  + task_fit_score * 0.05
```

## Implementation Plan

### Task 1: Candidate Registry

**Files:**
- Create: `docs/free-web-ai-candidates.md`
- Create: `data/free_web_ai_candidates.json`

- [x] Record Duck.ai, HeckAI, HIX, GPT.chat, DeepSeek mirrors, PLAI, GLM-AI, InstantSeek, and chat-gpt.org candidates.
- [x] For each candidate, record URL, access style, auth requirement, known models/evidence, and risk class.
- [x] Keep private-code routing disabled for all candidates by default.

### Task 2: Sandbox Probe Harness

**Files:**
- Create: `scripts/probe_free_web_ai.py`
- Create: `tests/test_free_web_ai_probe.py`

- [x] Add a CLI that sends harmless probes only.
- [x] Normalize responses into `ok`, `rate_limited`, `quota_exhausted`, `auth_expired`, `blocked`, `timeout`, or `unknown_error`.
- [x] Write JSON output under `data/free_web_ai_probe_results.json`.

### Task 3: Stability State

**Files:**
- Modify: `health_tracker.py`
- Modify: `probe_loop.py`
- Modify: `test_routing_engine.py`

- [x] Add backend state fields for auth/quota/manual-refresh conditions.
- [x] Add cooldown behavior for 429 and known quota messages.
- [x] Add regression tests for Kimi anonymous quota and SCNet/HTTP timeout cooldown.

### Task 4: Quota-Aware Routing

**Files:**
- Modify: `routing_engine.py`
- Modify: `router_v3.py`
- Modify: `budget_manager.py`

- [x] Add task-fit and remaining-quota signals to route selection.
- [x] Prefer healthy free backends for simple requests while preserving stronger capacity for complex coding.
- [x] Keep web candidates out of Claude Code/IDE routes until structured output is proven.

### Task 5: Closed-Loop Verification

**Files:**
- Update: `STATUS.md`
- Update: `docs/LIMA_MEMORY.md`
- Update: `docs/FREE_MODEL_ROUTING_STATUS.md`

- [x] Run local pytest for changed routing/stability modules.
- [x] Run local harmless probes.
- [x] Deploy only after local tests pass.
- [x] Smoke `http://47.112.162.80:8088/health`, `/v1/messages`, and `/v1/chat/completions`.
- [x] Record exact winners, failures, and cooldown decisions in docs.

## Current Decision

Do not add new no-login web AI sources directly to first-tier coding. `docs/FREE_WEB_AI_ADMISSION.md` is now the admission source of truth: DuckAI is admitted only as late fallback from existing local reverse evidence; page-only candidates remain sandbox-only.
