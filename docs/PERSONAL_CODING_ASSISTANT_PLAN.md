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
| `fast_coder` | `cerebras_gptoss`, `groq_gptoss`, `mistral_small` | Fastest acceptable full-fixture results: 80+ average score under 800ms average latency. |
| `primary_coder` | `github_gpt4o`, `github_gpt4o_mini`, `cerebras_gptoss`, `groq_gptoss` | Best current production balance after moving VPS-down local SCNet proxy models out of first position. |
| `strong_coder` | `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`, `scnet_qwen235b`, `scnet_ds_flash`, `scnet_ds_pro` | Full fixture winners first; VPS-working free SCNet models as strong fallback. |
| `fallback_coder` | `mistral_small`, `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `scnet_qwen30b`, `cf_kimi_k26` | Useful fallback capacity; CF Kimi is reachable but slow. |
| `disabled_or_late` | `scnet_large_ds_flash`, `scnet_large_ds_pro`, `scnet_minimax`, local `kimi*`, `stock_kimi_k2`, unauthorized/rate-limited providers | Local proxy down, timeout, invalid response, or auth/rate failures. |

### Free model activation

VPS smoke confirmed that not all registered free models are production-live. The current routing policy is:

- Use VPS-working direct SCNet models: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`.
- Keep `cf_kimi_k26` active for chat/fallback, not low-latency coding default.
- Keep local proxy Kimi and SCNet-large models registered but late until VPS ports `4504` and `4505` are running.
- Do not put `scnet_minimax` or `stock_kimi_k2` into default pools until their smoke failures are fixed.

Detailed evidence: `docs/FREE_MODEL_ROUTING_STATUS.md`.

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

## Definition Of Done

The personal coding assistant direction is closed when:

- `api.donglicao.com/v1/chat/completions` works from at least one IDE or terminal-agent client.
- At least three coding backends are ranked with evidence: fast, primary, and strong/fallback.
- Routing uses the ranking or a documented static tier map.
- A failed coding backend falls back without breaking the client request.
- A short daily/manual report can show backend successes, failures, and latency.
- Commercial docs/code do not appear in active plans or import paths.

## Next Steps

1. Validate the deployed endpoint from a real IDE or terminal-agent session.
2. Tune Claude Code/Cursor/Continue client-side config for lower latency and smaller request context.
3. Add per-session goal tracking only after context preflight proves useful in real coding work.
4. Re-run backend evals when keys/rate limits/local socket policy improve.
