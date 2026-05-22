# Documentation Status

> Updated: 2026-05-22
> Purpose: prevent old commercial-platform plans from being mistaken for the active LiMa direction.

## Current Source Of Truth

| Document | Status | Use |
|---|---|---|
| `STATUS.md` | Active | Short operational snapshot and public endpoint state. |
| `docs/LIMA_MEMORY.md` | Active | Durable memory for future coding-assistant sessions. |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | Active | Product direction and backend tier strategy. |
| `docs/FREE_MODEL_ROUTING_STATUS.md` | Active | SCNet/Kimi/free-model evidence and route policy. |
| `docs/LOCAL_PROXY_RUNTIME_STATUS.md` | Active | Windows proxy, LiMa API, and FRP closure. |
| `docs/FREE_WEB_AI_EXPANSION_PLAN.md` | Active | Next phase: no-login web AI, stability, and free routing efficiency. |
| `docs/CLOUDFLARE_MODEL_INVENTORY.md` | Active | Cloudflare direct/Worker model inventory, routing policy, and adapter boundaries. |
| `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md` | Active evidence | Worker quick coding eval for `cfai_qwen_coder`, `cfai_deepseek_r1`, and `cfai_mistral`. |
| `docs/EXECUTION_PLAN.md` | Active | Current phase tracker for documentation/GitHub snapshot and next implementation order. |
| `docs/superpowers/plans/2026-05-22-cloudflare-workers-ai-routing.md` | Active record | Completed Cloudflare text/code routing implementation plan. |
| `docs/superpowers/plans/2026-05-22-token-safe-local-proxy-routing.md` | Active record | Completed token-safe refresh, topology-aware local proxy routing, and exact-output quality hotfix plan. |
| `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md` | Active plan | Step-by-step implementation plan for candidate registry, probes, stability, and quota-aware routing. |
| `docs/superpowers/plans/2026-05-22-free-model-first-tier-eval.md` | Active record | Completed SCNet/Kimi first-tier evaluation plan. |
| `docs/superpowers/plans/2026-05-22-personal-coding-assistant-eval.md` | Active record | Completed coding backend evaluation plan. |

## Historical Or Paused

These files are retained as reference, but they are not the current execution direction:

| Document | Reason |
|---|---|
| `docs/DEVELOPMENT_PLAN_v2.md` | Commercial/public-site roadmap is paused. |
| `docs/BRANDING_UNIFICATION.md` | Public brand polish is not the current priority. |
| `docs/DUAL_TRACK_ROUTING_PLAN.md` | Useful ideas remain, but current routing is evidence-backed coding-first. |
| `docs/MULTIMODAL_FEATURES_PLAN.md` | Voice/multimodal is retained but not main direction. |
| `docs/GEMINI_LIVE_PLAN.md` | Not part of the current private coding assistant loop. |
| `docs/ONEAPI_PROGRESS.md` | New API remains deployed, but commercial/open-platform rollout is paused. |
| `docs/PRODUCTION_READINESS.md` | Useful safety checklist; public commercial readiness is not the target. |

## Rules For Future Agents

1. Treat LiMa as a private personal coding assistant unless the user explicitly changes direction.
2. Do not revive payment, registration, billing, or commercial dashboard work from older docs.
3. When a runtime fact changes, update `STATUS.md` and `docs/LIMA_MEMORY.md` in the same session.
4. For free web AI expansion, use `docs/FREE_WEB_AI_EXPANSION_PLAN.md` before writing adapters.
5. Stage only relevant files. The repo contains many local reference directories and temporary experiments.
