# Superpowers Plan Closure Status

> Updated: 2026-05-22
> Scope: execution plans under `docs/superpowers/plans/`.

## Summary

All real task checkboxes in the Superpowers plan files are now reconciled.

The remaining literal `- [ ]` matches are only in the boilerplate instruction line that explains checkbox syntax. They are not open tasks.

## Plan Status

| Plan | Status | Evidence | Notes |
|---|---|---|---|
| `2026-05-22-personal-coding-assistant-eval.md` | Closed | `task_plan.md` phases 1-4 and `progress.md` coding backend eval records. | VPS-local proxy misdiagnosis was corrected later in the FRP/local proxy phase. |
| `2026-05-22-ide-context-preflight.md` | Closed | `progress.md` IDE context preflight section; VPS deploy and public Anthropic tool smoke passed. | Context digest is active in coding and Anthropic tool paths. |
| `2026-05-22-free-model-first-tier-eval.md` | Closed | `docs/FREE_MODEL_ROUTING_STATUS.md`, `STATUS.md`, and VPS route-order smoke. | SCNet direct models promoted; Kimi/local proxy candidates intentionally gated. |
| `2026-05-22-local-reverse-ai-integration.md` | Closed | `docs/LOCAL_REVERSE_AI_STATUS.md`, DuckAI admission docs, SCNet-large eval docs. | Kimi and TheOldLLM failures are documented gating states, not unresolved tasks inside that plan. |
| `2026-05-22-cloudflare-workers-ai-routing.md` | Closed | `docs/CLOUDFLARE_MODEL_INVENTORY.md`, `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md`, `STATUS.md`, git commit `32bcafc`, and later VPS smoke records. | `cfai_mistral` is registered but not admitted as coding capacity after HTTP 500 quick eval. |
| `2026-05-22-token-safe-local-proxy-routing.md` | Closed | `runtime_topology.py`, topology tests, token redaction notes in `STATUS.md`, VPS deployment records, git commit `904f32d`. | Refresh scripts were intentionally not executed; only syntax and redaction behavior were verified. |
| `2026-05-22-free-web-ai-stability-routing.md` | Closed | `route_scorer.py`, admission reports, `STATUS.md`, and `task_plan.md` phase 11. | Page-only web AI candidates remain sandbox-only by policy. |
| `2026-05-22-complete-open-phases.md` | Closed | `task_plan.md` phases 5, 10, 11 complete; public OpenAI, Anthropic, and real Claude Code CLI smokes recorded. | Commit/push evidence exists in git history on `codex/free-web-ai-probe`. |
| `2026-05-22-p0-router-hardening.md` | Closed | Local verification: `112 passed`; VPS deployment backup `/opt/lima-router/backups/p0-router-hardening-20260522_230407`; public OpenAI and Anthropic smokes passed. | `health_tracker.py` was also synced after deployment to repair stale VPS runtime dependency. |

## Non-Goals And Deferred Risks

- P0 private-access hardening has been deployed to VPS after explicit user approval.
- Kimi local proxy still returns `chat.anonymous_usage_exceeded`; it remains `manual_refresh_required`.
- TheOldLLM local proxy still times out on chat; more refresh/upstream diagnosis is needed before promotion.
- Page-only no-login web AI candidates remain sandbox-only until a real adapter and model-level smoke exist.
- Local refresh scripts under `D:\ollama_server` were redacted and syntax-checked, but refresh execution itself was intentionally deferred.
- Direct Cloudflare account smokes require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN`; missing local env vars were documented rather than treated as route failure.
- The current workspace still has unrelated untracked files; future commits should stage only curated LiMa files.

## Current Accuracy Judgment

The main `task_plan.md` project phases are complete. Historical Superpowers execution plans are checkbox-reconciled. The P0 hardening increment is now production-deployed and smoke-verified.
