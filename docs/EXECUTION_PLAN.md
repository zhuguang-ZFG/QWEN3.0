# LiMa Execution Plan

> Updated: 2026-05-23
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
| 9. Dead code cleanup + streaming unification | Next | Remove dead modules; wire streaming path through routing_engine for retrieval/skills injection. |
| 10. server.py decomposition | Next | Split server.py from 2300+ lines toward <800 target; extract route handlers into focused modules. |

## Next Implementation Order

1. Delete confirmed dead code: `stats_collector.py`, verify and remove any other zero-caller modules.
2. Wire streaming path through `routing_engine.route()` so retrieval injection and skills injection apply to streaming requests.
3. Begin `server.py` decomposition: extract chat/completions handler, Anthropic handler, and streaming handler into `routes/` modules.
4. Consolidate `BACKENDS` to single source (eliminate `smart_router.BACKENDS` duplication).
5. Wire `key_pool.py` into `http_caller.py` for multi-key providers.
6. Run local tests, deploy only when requested, smoke public endpoints.

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
