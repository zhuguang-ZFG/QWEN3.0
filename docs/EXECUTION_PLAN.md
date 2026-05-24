# LiMa Execution Plan

> Updated: 2026-05-24
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
| 10. server.py decomposition | In Progress | server.py reduced from 2340 to 870 lines; 7 modules extracted, including `server_lifespan.py`, `chat_models.py`, and `chat_request_utils.py`. Chat/Anthropic handlers remain. |

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
- FRP `8088` is closed-loop again after hardening local Windows router startup:
  - local `8080` chat returned exact `lima-final-local-ok`;
  - public FRP `8088` chat returned exact `lima-final-frp-ok`;
  - `local_router_start.bat` now preserves/defaults the private API key environment for the router process.

## Next Implementation Order

1. Continue `server.py` decomposition: extract chat/completions handler and Anthropic handler into `routes/` modules in small slices.
2. Keep always-on worker daemon mode gated behind repo allowlist, runtime budget, stop marker, audit, failure quarantine, and manual production approval.
3. Keep gated web/local candidates out of normal routing until refresh and model-level smoke evidence exists.
4. Add deeper key-pool telemetry/concurrency tuning later only if provider load requires it.
5. Run local tests, deploy only when requested, smoke public endpoints.

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
