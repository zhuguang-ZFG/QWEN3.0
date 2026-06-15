# Superpowers Plan Closure Status

> Updated: 2026-05-26
> Scope: execution plans under `docs/superpowers/plans/`.

## Summary

The 2026-05-22 execution plans are reconciled and closed.

Several 2026-05-23/2026-05-24 plan files still contain unchecked implementation-plan checkboxes. Treat those files as historical execution drafts unless a current status document below says otherwise:

- `STATUS.md`
- `docs/EXECUTION_PLAN.md`
- `docs/LIMA_MEMORY_CN.md`
- `progress.md`

The current runtime truth is: VPS Server/Worker APIs are deployed, Agent Worker completed a public real-machine worker smoke, FRP `8088` chat is healthy again after local router startup hardening, `server.py` route decomposition is closed for this architecture pass, backend capability registry plus `key_pool.py` integration are deployed, redacted key-pool telemetry is implemented, the TechSpar-inspired mastery loop is implemented locally, the public LiMa Device Gateway is deployed with Redis HA task routing, and **WeChat product channels are retired** (`docs/WECHAT_RETIRED.md`).

**Open work prioritization:** `docs/NEXT_MILESTONES.md` (four tracks: coding backends, Agent Worker, ESP32/Device Gateway, code quality).

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
| `2026-05-23-lima-server-agent-evolution.md` | Implemented/closed by evidence | Server task contract, role/eval/evolution modules, protected task APIs, and focused tests are recorded in `STATUS.md` and `docs/LIMA_MEMORY_CN.md`. | The plan file still has draft checkboxes; use status docs as truth. |
| `2026-05-23-retired-agent-cli-agent-worker.md` | Implemented/closed by evidence | `D:\GIT\retired CLI` has `/lima task`, `/lima next`, bounded `/lima work`, audit, quarantine, repo allowlist, and full test evidence. | The plan file still has draft checkboxes; use status docs as truth. |
| `2026-05-23-lima-server-control-plane-v03-for-ai-worker.md` | Implemented locally and deployed as part of later sync | Admin audit, Telegram review helpers, candidate extraction, and contract smoke evidence are recorded in `STATUS.md` and `docs/LIMA_MEMORY_CN.md`. | VPS worker APIs were deployed on 2026-05-24. |
| `2026-05-23-lima-real-machine-worker-v04.md` | Deployed and smoke-verified | Live task `cfcd3f2b` was created, executed by Agent Worker, submitted as `needs_review`, and confirmed with events `created,result_submitted`. | This supersedes the earlier "No production deployment was performed" note. |
| `2026-05-23-lima-autonomous-worker-v02.md` | Partially implemented | Bounded work loops, stop marker, failure quarantine, repo allowlist, audit, and runtime budget exist in Agent Worker. | Always-on daemon mode remains deferred and gated. |
| `2026-05-23-techspar-mastery-loop.md` | Implemented and deployed | `mastery_loop/` has typed records, SQLite store, event adapters, scoring, weak-point extraction, review scheduling, recommendations, and traces; skill promotion requires mastery evidence. VPS backup `/opt/lima-router/backups/mastery-loop-20260524-125511`; HTTPS/FRP/preflight smokes passed. | Admin UI exposure and hot-path planner/routing influence remain deferred and gated. |
| `2026-05-24-tool-dispatcher-clean-split.md` | Closed locally and deployed as runtime files | Split `lima_fc_tools` runtime files were part of the 2026-05-24 VPS sync; focused tests and full pytest evidence are in `STATUS.md`. | Telegram FC/TTS remains outside ordinary routing by policy. |
| `2026-05-24-lima-direct-device-gateway.md` | Public route deployed; Redis HA follow-up deployed | Public `/device/v1/*` route, fake U8 local/public smokes, Redis task store/session bus, cross-process temp-router smoke, and `12/12` online distribution smoke are recorded in `STATUS.md`, `docs/LIMA_MEMORY_CN.md`, and `progress.md`. | Real U8 firmware and real hardware motion remain gated. |
| `2026-05-25-lima-device-gateway-ha.md` | Implemented and deployed | Redis service, Python Redis client, HA env vars, loopback Redis binding, public `6379` guard, cross-process delivery smoke, and focused tests are recorded in the plan and status docs. | Main service worker-count increase remains a separate rollout switch. |

## Non-Goals And Deferred Risks

- P0 private-access hardening has been deployed to VPS after explicit user approval.
- Kimi local proxy still returns `chat.anonymous_usage_exceeded`; it remains `manual_refresh_required`.
- TheOldLLM local proxy still times out on chat; more refresh/upstream diagnosis is needed before promotion.
- Page-only no-login web AI candidates remain sandbox-only until a real adapter and model-level smoke exist.
- Local refresh scripts under `D:\ollama_server` were redacted and syntax-checked, but refresh execution itself was intentionally deferred.
- Direct Cloudflare account smokes require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN`; missing local env vars were documented rather than treated as route failure.
- The current workspace still has unrelated untracked files; future commits should stage only curated LiMa files.
- `server.py` route decomposition, backend configuration consolidation, `key_pool.py` integration, and key-pool telemetry are closed by the 2026-05-24 endpoint/key-pool closure deploy.
- Kimi local proxy, TheOldLLM, MiMo web, and page-only web AI candidates remain gated until refresh and model-level smoke evidence exists.
- Always-on worker daemon mode remains deferred behind repo allowlist, runtime budget, stop marker, audit, failure quarantine, and manual production approval.
- Mastery-loop admin exposure and automatic planner/routing influence remain deferred until private admin views and focused safety tests exist.

## Current Accuracy Judgment

The main `task_plan.md` project phases are complete. 2026-05-22 Superpowers execution plans are checkbox-reconciled. Later plan files may still contain draft checkboxes, but current runtime status is calibrated in `STATUS.md`, `docs/EXECUTION_PLAN.md`, `docs/LIMA_MEMORY_CN.md`, and `progress.md`; latest VPS evidence includes Device Gateway Redis HA backup `/opt/lima-router/backups/codex-device-ha-20260525_015208`, online distribution smoke `12/12`, and worker preflight `ready=true`. The remaining reference-project work is intentionally gated policy work, not an unimplemented migration plan.
