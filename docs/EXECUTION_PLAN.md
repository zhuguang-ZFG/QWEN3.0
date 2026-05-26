# LiMa Execution Plan

> Updated: 2026-05-26
> Status: current plan for the private personal coding assistant direction
> Supersedes: older commercial/open-platform sprint plans

## Direction

LiMa is a private coding assistant backend. The current goal is to make real IDEs and terminal coding agents get better answers from the available free and paid-ish backend pool.

Paused work:

- Public commercial launch.
- Payment and billing.
- Public registration.
- Commercial dashboard polish.
- Marketing-site roadmap.

## Current Runtime

| Area | State |
|---|---|
| HTTPS entry | `https://chat.donglicao.com/v1` works for private OpenAI/Anthropic-compatible access. |
| FRP entry | `http://47.112.162.80:8088/v1` maps VPS `8088` to Windows LiMa API `8080`. |
| IDE key/model | `lima-local` with model `lima-1.3`. |
| Direct SCNet models | `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, and `scnet_ds_pro` are first-tier coding candidates. |
| SCNet-large local proxy | Windows `D:\ollama_server` port `4505` is running and must be tested through the Windows local-router path. |
| Kimi local proxy | Windows port `4504` runs, but chat currently fails with anonymous quota exhaustion and needs session refresh. |
| New API | `api.donglicao.com` is retained, but requires real New API tokens and is not the active private IDE path. |
| Device Gateway | `https://chat.donglicao.com/device/v1/*` is public behind per-device auth; VPS uses Redis task queues and Redis pub/sub session-owner notification for multi-process delivery. |

## Active Phases

| Phase | Status | Exit Criteria |
|---|---|---|
| 1. Personal coding assistant reset | Complete | Commercial docs/code no longer drive active work. |
| 2. Coding backend evaluation | Complete | Repeatable coding fixtures and backend ranking exist. |
| 3. SCNet/Kimi first-tier evaluation | Complete | Direct SCNet promoted; Kimi kept fallback/inactive until fixed. |
| 4. Local proxy + FRP closure | Complete | VPS `8088` reaches Windows `8080`; public health/models/chat smokes pass. |
| 5. Documentation/GitHub snapshot | Complete | Status, memory, plans, and reference evaluation reflect latest local reality. |
| 6. Knowledge retrieval injection | Complete | Graph/code retrieval results injected into prompts; retrieval trace recorded; admin endpoint exposed. |
| 7. Always-on typed memory | Complete | 10 typed memory kinds, inbox ingestion daemon, background consolidation, wired into server lifespan. |
| 8. MCP knowledge/memory tools | Complete | `/mcp/tools/list` and `/mcp/tools/call` expose search_repo, search_memory, get_retrieval_trace. |
| 9. Dead code cleanup + streaming unification | Complete | stats_collector.py deleted; streaming path wired through inject_retrieval_context. |
| 10. server.py decomposition | Complete for current architecture pass | server.py is reduced to app setup plus core runtime helpers; chat, Anthropic, system, lifespan, models, request helpers, streaming helpers, admin, images, embeddings, and worker routes are extracted. |
| 11. TechSpar-inspired mastery loop | Complete locally | `mastery_loop/` records sanitized evidence, module mastery, weak points, review schedules, recommendations, and traces; skill promotion requires mastery evidence. |
| 12. Device Gateway public + Redis HA | Complete for current VPS topology | `/device/v1/*` is public through chat nginx; Redis-backed task store/session bus are deployed; cross-process temporary-router smoke and fake U8 public smoke passed. |
| 13. Telegram × GitHub operator channel | **Active** | CQ-GH-001 webhook done; TG-GH-2~6 per `docs/superpowers/plans/2026-05-26-telegram-github-maximization.md`. |
| 14. Cloudflare × Google free-tier maximization | **Active (P1)** | CF-G-0~6 per `docs/superpowers/plans/2026-05-26-cloudflare-google-maximization.md`; parallel after TG-GH-1. |
| 15. Provider model auto-discovery | **Paused (archived plan)** | `docs/superpowers/plans/2026-05-26-provider-model-automation-full-plan.md`; CF-G-2 merges PA-B. |

## 2026-05-24 Runtime Closure

- VPS deployment of Server worker preflight/smoke-task APIs is complete.
- `server_lifespan.py` is deployed on VPS after backup `/opt/lima-router/backups/lifespan-extract-20260524_111647`.
- `chat_models.py` is deployed on VPS after backup `/opt/lima-router/backups/chat-models-extract-20260524_113220`; `server.py` re-exports `Message`, `ChatRequest`, and `extract_system_prompt` for compatibility.
- `chat_request_utils.py` is deployed on VPS after backup `/opt/lima-router/backups/chat-request-utils-20260524_114403`; OpenAI and Anthropic request text/preview extraction now share this helper.
- `D:\GIT\deepcode-cli` completed public task `cfcd3f2b` through the deployed Server and submitted `needs_review`.
- Post-extraction checks passed: local focused regression `40 passed`; remote compile/import passed; HTTPS chat returned exact `deploy_https_ok_1134`; FRP chat returned exact `lima-chat-models-frp-ok`; worker preflight returned `ready=true`.
- Post-request-helper checks passed: local focused regression `45 passed`; remote compile/import passed; HTTPS chat returned exact `request_utils_https_ok`; FRP chat returned exact `request_utils_frp_ok`; worker preflight returned `ready=true`.
- Backend registry/key-pool closure is deployed on VPS after backup `/opt/lima-router/backups/backend-registry-keypool-20260524-120642`.
  - `backends.py` is the shared source for proxy/capability sets used by `smart_router.py` and reflection routing.
  - `http_caller.py` uses `key_pool.py` for provider key selection, env bootstrap via `LIMA_KEY_POOL_<PROVIDER>`, and success/failure feedback.
  - Verification passed: focused registry/key-pool suite `58 passed`; expanded runtime regression `110 passed`; secret/request/vision/free-web admission suite `10 passed`; remote compile/import passed.
  - Public smokes passed: HTTPS exact `backend_registry_https_ok`; FRP exact `backend_registry_frp_ok`; worker preflight `ready=true`.
- Endpoint/key-pool closure is deployed on VPS after backup `/opt/lima-router/backups/endpoints-keypool-closed-20260524-123145`.
  - `routes/chat_endpoints.py` owns OpenAI and Anthropic HTTP endpoint parsing.
  - `routes/system_endpoints.py` owns models, health, live-key, and status endpoints.
  - `key_pool.pool_snapshot()` exposes redacted active/cooled/blocked telemetry for provider pools.
  - Verification passed: endpoint/key-pool focused suite `62 passed`; expanded runtime regression `128 passed`; remote compile/import passed.
  - Public smokes passed: HTTPS exact `endpoints_closed_https_ok`; FRP exact `endpoints_closed_frp_ok`; worker preflight `ready=true`.
- Mastery-loop closure is deployed on VPS after backup `/opt/lima-router/backups/mastery-loop-20260524-125511`:
  - `mastery_loop/` contains typed models, SQLite-backed storage, event adapters, scoring, weak-point extraction, scheduling, recommendations, and traces.
  - `agent_evolution.promote_candidate()` requires eval pass, manual approval, and non-empty mastery evidence refs.
  - `/agent/skills/{skill_id}/promote` enforces the same evidence gate.
  - Focused regression covers mastery storage/adapters/scoring/recommendations and route-level promotion behavior.
  - Remote `py_compile` and import smoke passed; public smokes passed: HTTPS exact `mastery_loop_https_ok`; FRP exact `mastery_loop_frp_ok`; worker preflight `ready=true`.
- FRP `8088` is closed-loop again after hardening local Windows router startup:
  - local `8080` chat returned exact `lima-final-local-ok`;
  - public FRP `8088` chat returned exact `lima-final-frp-ok`;
  - `local_router_start.bat` now preserves/defaults the private API key environment for the router process.

## 2026-05-25 Device Gateway Public And Redis HA Closure

- Public `/device/v1/*` is exposed through `chat.donglicao.com` and guarded by per-device tokens.
- VPS Device Gateway health reports `task_store.backend=redis` and `session_bus.backend=redis`.
- Redis is bound to loopback; public `6379` is included in online distribution port-guard smoke.
- Cross-process proof: a private temp router on `127.0.0.1:18080` created a task delivered to the public main WebSocket session through Redis pub/sub.
- Verification passed: focused Device Gateway suite `31 passed`; expanded agent/device subset `45 passed`; online distribution smoke `12/12`.

## Next Implementation Order

**当前 P0 主线：** `docs/superpowers/plans/2026-05-26-telegram-github-maximization.md`

1. **TG-GH-1** — frpc/Clash 自启 + Telegram 出站 smoke
2. **TG-GH-2** — LiMa Code → Telegram 任务生命周期推送（deepcode-cli）
3. **TG-GH-3** — 统一 Operator 早报（health + GitHub + tasks + **CF/Google 配额**）
4. **TG-GH-4** — Telegram `/github` `/device` 命令

**并行 P1（免费 API 额度）：** `docs/superpowers/plans/2026-05-26-cloudflare-google-maximization.md`

5. **CF-G-0** — CF/Google 模型 inventory 脚本 + diff 报告（零路由风险）
6. **CF-G-1** — `budget_manager` 补全 `cf_*` + 配额 Telegram 告警
7. **CF-G-2/3** — CF 扩容 smoke + Google chat_fast/vision 优化

四线优先级见 **`docs/NEXT_MILESTONES.md`**（编码后端 / LiMa Code Worker / ESP32·Device Gateway / 代码质量）。

5. **代码质量 P0** — chunked body 413、`/api/live-key` 不泄钥（进行中）
6. **编码后端** — Kimi/SCNet-large refresh + eval
7. **Provider model automation** — 存档计划，TG-GH-3 后再启 PA-A
8. **ESP32** — PROD-003 真机 smoke
9. Run local tests; deploy when slice complete; smoke public endpoints.

**已关闭方向**：微信真机/机器人（`docs/WECHAT_RETIRED.md`）；商业支付/注册。

## Verification Commands

```powershell
python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
python -m pytest -q tests .\test_routing_engine.py .\test_rate_limiter.py .\test_http_caller.py .\test_dual_track.py .\test_code_orchestrator.py .\test_streaming.py .\test_skills_injector.py --ignore=active_model
curl.exe --noproxy "*" -sS --max-time 15 http://47.112.162.80:8088/health
curl.exe --noproxy "*" -sS --max-time 15 http://47.112.162.80:8088/v1/models -H "Authorization: Bearer lima-local"
```

Chat smoke should use JSON serialization from Python or a known-good client to avoid PowerShell quoting issues.

## Source Documents

- `STATUS.md`
- `docs/DOCUMENTATION_STATUS.md`
- `docs/LIMA_MEMORY.md`
- `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`
- `docs/FREE_MODEL_ROUTING_STATUS.md`
- `docs/LOCAL_PROXY_RUNTIME_STATUS.md`
- `docs/FREE_WEB_AI_EXPANSION_PLAN.md`
- `docs/REFERENCE_PROJECT_EVALUATION.md`
- `docs/reference/TECHSPAR_BORROWING_NOTES.md`
- `docs/superpowers/plans/2026-05-26-telegram-github-maximization.md`
- `docs/superpowers/plans/2026-05-26-provider-model-automation-full-plan.md`
- `docs/superpowers/plans/2026-05-26-cloudflare-google-maximization.md`
