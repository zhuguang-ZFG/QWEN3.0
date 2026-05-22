# LiMa Execution Plan

> Updated: 2026-05-22
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
| 5. Documentation/GitHub snapshot | In progress | Status, memory, plans, and GitHub reflect latest reality. |
| 6. Free web AI expansion | Next | More no-login web AI candidates are found and sandbox-probed. |
| 7. Stability improvements | Next | Token/session refresh, quota detection, and rate-limit cooldown are implemented. |
| 8. Free routing optimization | Next | Free backends are selected by quality, health, latency, quota, and task fit. |

## Next Implementation Order

1. Create a candidate registry for Duck.ai, HeckAI-like sites, and other no-login web AI surfaces.
2. Build a sandbox probe harness that sends harmless prompts and normalizes failure classes.
3. Add backend state for `auth_expired`, `quota_exhausted`, `anonymous_usage_exceeded`, `captcha_required`, and `manual_refresh_required`.
4. Add quota-aware routing so free backends are used aggressively for simple work but protected for valuable coding requests.
5. Run local tests, deploy once, smoke public endpoints, and update `STATUS.md` plus `docs/LIMA_MEMORY.md`.

## Verification Commands

```powershell
python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
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
