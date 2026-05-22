# LiMa Memory

> Updated: 2026-05-22
> Purpose: durable working memory for future LiMa coding-assistant sessions.

## Current Direction

LiMa is now a private personal coding assistant backend, not a commercial public platform.

Primary goal:

- Make Cursor, Continue, Claude Code, Codex-like terminal agents, and private chat use the best available coding backends.
- Prefer evidence-backed routing over adding complexity.
- Keep the VPS simple: nginx HTTPS, private API access, lima-router on localhost, minimal moving parts.

Paused or removed direction:

- Public registration.
- Payments.
- Billing ledger and quota accounting.
- Commercial dashboard work.
- Public open-platform product polish.

## Production Topology

| Component | Current Role |
|---|---|
| `chat.donglicao.com` | Public HTTPS entry for private chat and `/v1/*` proxy to LiMa. |
| `api.donglicao.com` | New API/open-platform UI still exists, but commercial rollout is paused. |
| `lima-router` | Python/FastAPI router on VPS, local port `8080`. |
| New API | Local port `3003`, still retained for existing API gateway state. |
| Voice gateway | Local port `8091`, retained but not the main direction. |

Public direct access to internal ports `3000`, `3001`, `3003`, `8080`, and `8091` is blocked. nginx remains the external boundary.

## Active Runtime Files

| File | Responsibility |
|---|---|
| `server.py` | Compatibility entry for OpenAI and Anthropic requests. |
| `routing_engine.py` | Main scenario classification and route execution. |
| `router_v3.py` | Backend pool definitions and selection. |
| `code_orchestrator.py` | Coding-specific context engineering, backend tiering, quality gate, and repair. |
| `http_caller.py` | Unified backend HTTP calls. |
| `lima_context.py` | Request-local context preflight digest. |
| `health_tracker.py` | Backend health and cooldown. |
| `budget_manager.py` | Backend budget availability and priority. |
| `backends.py` | Backend inventory. |

## Coding Backend Evidence

Broad smoke:

- 85 coding-like candidates tested.
- 16 passed the first `code_review` smoke.

Full three-case fixture winners:

- `scnet_large_ds_flash` passed locally, but VPS proxy `4505` is currently down, so it is not first in production pools.
- `github_gpt4o`
- `github_gpt4o_mini`
- `or_gptoss_120b`

Fast usable coding tier:

- `cerebras_gptoss`
- `groq_gptoss`
- `mistral_small`
- `groq_gptoss_20b` for simpler cases and tool path speed.

## Free Model Status

VPS-working SCNet direct models:

- `scnet_ds_flash`
- `scnet_ds_pro`
- `scnet_qwen235b`
- `scnet_qwen30b`

Slow or inactive:

- `scnet_minimax` timed out in VPS smoke.
- `scnet_large_ds_flash` and `scnet_large_ds_pro` require local proxy `4505`, currently refused on VPS.
- `cf_kimi_k26` works but is slow, so it is chat/fallback capacity.
- `kimi`, `kimi_thinking`, and `kimi_search` require local proxy `4504`, currently refused on VPS.
- `stock_kimi_k2` returned invalid JSON/empty response in smoke.

See `docs/FREE_MODEL_ROUTING_STATUS.md` for the detailed table.

## Claude Code / Anthropic Tool Route

Claude Code requests with tools enter `/v1/messages`, not the normal OpenAI chat path.

Current optimized behavior:

- `TOOL_TIER1_BACKENDS` starts with fast OpenAI-compatible tool-capable backends.
- Tool retries iterate distinct backends rather than retrying the same failed backend repeatedly.
- Anthropic messages are converted to OpenAI-compatible messages.
- `lima_context.py` injects a compact `LiMa context preflight` block before forwarding.

Known-good public smoke:

- `https://chat.donglicao.com/v1/messages`
- Status 200.
- `stop_reason=tool_use`.
- Latest final smoke after context-preflight sync: 600ms.

## Context Preflight

Implemented behavior:

- Extracts IDE source, workspace hints, task shape, likely language, mentioned files, and tool/error signals from request-local data.
- Does not claim to read the user's local workspace from the VPS.
- Injects into normal coding route and Anthropic tool route.

Verification:

- `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py`
- Latest known result before this document update: `70 passed`.

## Deployment Practice

Superpowers rule:

- Write or update plan/docs first for non-trivial work.
- Test locally.
- Backup remote files.
- Upload only changed runtime files.
- Remote compile.
- Restart `lima-router`.
- Smoke `/health` and a real public endpoint.
- Update `task_plan.md`, `findings.md`, and `progress.md`.

Recent backups:

- `/opt/lima-router/backups/speed-20260522_181808`
- `/opt/lima-router/backups/context-preflight-20260522_183133`
- `/opt/lima-router/backups/context-preflight-sync-20260522_183423`
- `/opt/lima-router/backups/free-model-routing-20260522_184556`

Restart caveat:

- `systemctl restart lima-router` can hang in `deactivating` while uvicorn waits for open streaming/tool connections.
- Observed recovery command sequence:

```bash
systemctl kill -s SIGKILL lima-router || true
systemctl reset-failed lima-router || true
systemctl start lima-router
curl -sS -m 10 -w '\n%{http_code}' http://127.0.0.1:8080/health
```

Latest free-model routing deployment:

- Local tests: `71 passed in 0.52s`.
- VPS `/health`: 200.
- Public coding smoke: 200 in 4585ms.
- Public Anthropic tool smoke: 200 in 672ms with `stop_reason=tool_use`.

## Current Risks

- Some registered backends require local proxy services that are not running on the VPS.
- Kimi free models are not all usable yet; only CF Kimi is currently reachable.
- SCNet direct models are usable, but coding quality still needs full fixture evaluation from the VPS.
- The repo contains many local reference directories and temporary scripts; do not stage them blindly.
- `server.py` is still large and should be split later, but not during routing experiments.

## Next Task Waiting State

User asked to finish this documentation/GitHub upload first, then wait for the next instruction.

Do not start the next feature without user direction.
