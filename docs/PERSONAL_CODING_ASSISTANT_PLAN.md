# LiMa Personal Coding Assistant Plan

> Date: 2026-05-22
> Status: Active direction
> Replaces: commercial open-platform roadmap, payment, public registration, and billing plans.

## Goal

Turn LiMa into a private coding assistant backend for the owner. The system should help Cursor, Continue, VS Code, Claude Code/Codex-like terminal agents, and the private chat page choose the best coding backend from the available model pool.

This is not a public commercial platform. It does not need payments, public registration, multi-tenant billing, marketing pages, or a complex customer admin flow.

## Non-Goals

- No public user registration.
- No self-serve payments.
- No public quota sales.
- No customer-facing commercial dashboard.
- No voice-first product direction.
- No broad model marketplace positioning.

## Target Architecture

```text
IDE / terminal agent / private chat
  -> private API key or trusted network boundary
  -> api.donglicao.com or chat.donglicao.com
  -> lima-router
  -> coding backend candidate pool
  -> scoring and fallback
  -> response
  -> request log + backend score update
```

## Kept Components

| Component | Role |
|---|---|
| `api.donglicao.com` | OpenAI-compatible endpoint for IDEs and agents. |
| `chat.donglicao.com` | Private/manual debugging and quick coding chat. |
| `server.py` | Compatibility boundary for OpenAI/Anthropic requests. |
| `routing_engine.py` | Main routing decision layer. |
| `http_caller.py` | Backend invocation and timeout handling. |
| `health_tracker.py` | Runtime backend health signal. |
| `backends.py` / `api_config.json` | Backend inventory. |
| `docs/MODEL_CATALOG.md` | Initial model capability hints. |

## Removed Or Paused Components

| Component | Status | Reason |
|---|---|---|
| `commercial_config.py` | Removed | Billing flag and pricing logic are not needed. |
| `quota_ledger.py` | Removed | Personal assistant does not need prepaid accounting. |
| `usage_store.py` | Removed | Billing-grade usage store is too heavy for this phase. |
| Commercial auth tests | Removed | Replaced later by a small private-access check if needed. |
| Commercial roadmap and payment docs | Removed | Wrong product direction. |
| Public open-platform upgrade docs | Removed | Public product polish is not the current goal. |

## Backend Selection Strategy

The first real task is to identify coding-capable backends with evidence instead of assumptions.

### Current evidence-backed tiers

| Tier | Backend | Evidence |
|---|---|---|
| `fast_coder` | `scnet_qwen30b`, `scnet_ds_flash`, `scnet_qwen235b`, `cerebras_gptoss`, `groq_gptoss` | SCNet direct models passed VPS first-tier eval; Cerebras/Groq stay as fast alternatives. |
| `primary_coder` | `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o` | Direct SCNet models passed production VPS fixtures and now lead coding pools. |
| `strong_coder` | `scnet_ds_flash`, `scnet_qwen235b`, `scnet_ds_pro`, `scnet_qwen30b`, `github_gpt4o`, `or_gptoss_120b` | SCNet first-tier winners plus previous deep reasoning winners. |
| `fallback_coder` | `mistral_small`, `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `scnet_qwen30b`, `cf_kimi_k26` | Useful fallback capacity; CF Kimi is reachable but slow. |
| `disabled_or_late` | `scnet_large_ds_flash`, `scnet_large_ds_pro`, `scnet_minimax`, local `kimi*`, `stock_kimi_k2`, unauthorized/rate-limited providers | SCNet-large local proxy is running but needs route-path fixture rerun; Kimi local proxy needs re-login; others timeout, invalid response, or auth/rate failures. |

### Free model activation

VPS smoke confirmed that not all registered free models are production-live. The current routing policy is:

- Use VPS-working direct SCNet models as first-tier coding capacity: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`.
- Keep `cf_kimi_k26` active for chat/fallback, not low-latency coding default.
- Keep SCNet-large local proxy models registered and ready for route-path eval through Windows `8080`; keep local Kimi late until its session is refreshed.
- Do not put `scnet_minimax` or `stock_kimi_k2` into default pools until their smoke failures are fixed.

Detailed evidence: `docs/FREE_MODEL_ROUTING_STATUS.md` and `data/free_model_first_tier_eval.json`.

### Candidate tiers

| Tier | Purpose | Example policy |
|---|---|---|
| `fast_coder` | Small edits, explanations, command help | Low latency and acceptable code quality. |
| `primary_coder` | Default IDE/agent coding requests | Best balance of correctness, latency, and stability. |
| `strong_coder` | Complex bugs, multi-file reasoning, architecture | Highest pass rate, latency tolerated. |
| `fallback_coder` | Recovery when the selected tier fails | Stable and cheap enough to keep warm. |
| `disabled` | Poor quality, high failure rate, or unstable | Excluded from normal routing. |

### Evaluation dimensions

- Fix a failing Python function.
- Generate a small utility with tests.
- Explain unfamiliar code concisely.
- Produce structured JSON/tool-call-safe output.
- Follow a multi-step coding instruction without adding unrelated changes.
- Keep latency within acceptable bounds.
- Avoid refusal, empty response, malformed response, and obvious hallucination.

## Minimal Evaluation Loop

```text
coding case fixture
  -> send same prompt to candidate backends
  -> collect answer, latency, status, error
  -> grade with deterministic checks where possible
  -> store backend score JSON
  -> update recommended tier mapping
```

Initial artifacts:

- `evals/coding_cases/`: small coding prompts and expected properties.
- `scripts/eval_coding_backends.py`: batch runner.
- `data/coding_backend_scores.json`: score table.
- `docs/CODING_BACKEND_RANKING.md`: human-readable result.

## Runtime Rules

- Prefer `primary_coder` for IDE/agent traffic.
- Use `fast_coder` for short explanation and simple transform requests.
- Use `strong_coder` for large context, debugging, architecture, and repeated failures.
- If a backend returns an error, empty response, timeout, or low-quality marker, retry once on the next tier.
- Log only metadata needed for improvement: backend, latency, status, request type, and a short redacted prompt preview.

## Context Preflight

The first Cursor-inspired improvement is request-local context preflight. LiMa does not index or read the user's local workspace from the VPS; it only summarizes context already present in the incoming request.

Implemented behavior:

- `lima_context.py` builds a compact `LiMa context preflight` block.
- It extracts IDE source, workspace hints, task shape, likely language, mentioned file paths, and tool/error signals.
- `code_orchestrator.enhance_context` appends the digest for normal coding routes.
- `server._inject_anthropic_context_preflight` appends the same digest for Claude Code Anthropic `/v1/messages` tool routes.
- The digest includes an explicit boundary: the VPS cannot directly read the user's local workspace.

Verified on 2026-05-22:

- Local compile passed for `lima_context.py`, `code_orchestrator.py`, `server.py`, `routing_engine.py`, and `router_v3.py`.
- Local tests returned `70 passed in 0.51s`.
- VPS deployment backup: `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Final no-BOM sync backup: `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- VPS local `/health` returned 200 after restart.
- Final public Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## VPS Simplification

Keep the current production safety fixes:

- Public internal ports stay blocked.
- HTTPS stays on nginx.
- Basic security headers stay.
- New API database backup may remain because it is cheap and protects current platform state.

Simplify future VPS work:

- No more public registration work.
- No payment setup.
- No billing tables.
- No commercial dashboard endpoints.
- No deploy gates tied to quota or admin commercial stats.

## Next Phase: Free Web AI And Stability

The next direction is to expand capacity without sacrificing the coding experience.

| Workstream | Goal | First Artifact |
|---|---|---|
| No-login web AI discovery | Find DuckAI/HeckAI-style sources that can be probed safely. | `docs/FREE_WEB_AI_EXPANSION_PLAN.md` |
| Backend stability | Normalize token/session expiry, quota exhaustion, rate limits, and provider cooldown. | Stability tests around `health_tracker.py` and `probe_loop.py`. |
| Free routing efficiency | Spend free backends on the right requests instead of static ordering only. | Quota/quality/latency scoring in `routing_engine.py` and `router_v3.py`. |

Rules:

- New web AI candidates start in sandbox only.
- Do not send private code to untrusted web candidates until they pass admission checks.
- Treat Duck.ai as first candidate because it has the strongest current confidence signal.
- Treat HeckAI-style mirrors as research candidates until request shape, rate limits, and ToS risk are clear.
- Study 9Router and OmniRoute for routing patterns, but do not replace LiMa's current router wholesale.

## Definition Of Done

The personal coding assistant direction is closed when:

- `api.donglicao.com/v1/chat/completions` works from at least one IDE or terminal-agent client.
- At least three coding backends are ranked with evidence: fast, primary, and strong/fallback.
- Routing uses the ranking or a documented static tier map.
- A failed coding backend falls back without breaking the client request.
- A short daily/manual report can show backend successes, failures, and latency.
- Commercial docs/code do not appear in active plans or import paths.

## Next Steps

1. Inject graph/code retrieval results into prompts with trace evidence.
2. Add a lightweight always-on memory daemon and inbox ingestion outside the hot path.
3. Extend Session Memory into typed memories for project facts, code facts, ops events, tests, routing lessons, and reference patterns.
4. Add `lima-mcp` tools for repo search, memory search, retrieval traces, and `ask_lima` after local retrieval/memory traces prove useful.
5. Re-run backend evals when keys, rate limits, or local socket policy improve.

## 2026-05-23 Reference Architecture Update

Two external projects were reviewed against LiMa's current code state:

| Project | Value To LiMa | Decision |
|---|---|---|
| OpenRAG (`langflow-ai/openrag`) | Knowledge ingestion, retrieval observability, MCP knowledge access, mature document parsing patterns. | Borrow patterns; do not adopt the full platform or OpenSearch/Langflow stack yet. |
| Google Cloud always-on-memory-agent | Background memory ingestion, SQLite-first store, periodic consolidation, memory citations. | Use as the stronger reference for LiMa's next memory layer. |

Current LiMa has many primitives already, but the next useful step is depth rather than more modules:

- Graph retrieval should feed prompt context, not only compute reranked candidates.
- Session Memory should gain typed memory and async consolidation, not just raw turn summaries.
- The request path should expose retrieval/memory traces for debugging.

Detailed evaluation: `docs/REFERENCE_PROJECT_EVALUATION.md`.
