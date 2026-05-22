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

## Client Configuration

Use these for real IDE or terminal-agent validation:

```text
Primary base URL: https://chat.donglicao.com/v1
FRP base URL:     http://47.112.162.80:8088/v1
API key:          lima-local
Model:            lima-1.3
```

Do not use `api.donglicao.com` with `lima-local`; that host is still the New API gateway and returns `401 Invalid token` unless a real New API token is used.

## Local Proxy And FRP Closure

Current closed loop:

```text
IDE/client
  -> http://47.112.162.80:8088/v1
  -> VPS frps 8088
  -> Windows frpc redcode-api
  -> Windows LiMa API 127.0.0.1:8080
  -> Windows local providers on 4504/4505 when selected
```

Verified facts:

- `frpc.exe` registers `redcode-api` successfully.
- VPS `8088/tcp` is open in `firewalld`.
- `http://47.112.162.80:8088/health`, `/v1/models`, and `/v1/chat/completions` returned HTTP 200.
- `D:\GIT\local_router_start.bat` now starts `server.py` on Windows port `8080` and starts FRP if needed.
- Windows `4505` SCNet-large proxy is running and chat-compatible.
- Windows `4504` Kimi proxy is running, but chat currently fails with anonymous quota exhaustion.

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

- `scnet_large_ds_flash` passed locally; Windows local proxy `4505` is running. The earlier VPS `localhost:4505` failure was the wrong health check for the local-proxy architecture.
- `github_gpt4o`
- `github_gpt4o_mini`
- `or_gptoss_120b`

Fast usable coding tier:

- `cerebras_gptoss`
- `groq_gptoss`
- `mistral_small`
- `groq_gptoss_20b` for simpler cases and tool path speed.

Cloudflare coding capacity:

- Direct `cf_*` account API models are registered in `backends.py`; they require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN`.
- Worker `cfai_*` models use `https://ai.zhuguang.ccwu.cc/v1/chat/completions` and do not expose account credentials to LiMa clients.
- `cf_qwen_coder` and `cfai_qwen_coder` now enter the default `router_v3` code fallback window after SCNet/GitHub winners.
- `code_orchestrator.POOLS["coder"]` now includes `cf_qwen_coder`, `cfai_qwen_coder`, `cf_gptoss_120b`, `cf_deepseek_r1`, `cf_qwen3_30b`, and `cfai_deepseek_r1`.

## Free Model Status

VPS first-tier SCNet direct models:

- `scnet_ds_flash`
- `scnet_ds_pro`
- `scnet_qwen235b`
- `scnet_qwen30b`

These four passed the three-case production VPS coding fixture on 2026-05-22. Current route policy puts them at the front of coding pools, with `scnet_ds_pro` after the faster SCNet models.

Slow or inactive:

- `scnet_minimax` timed out in VPS smoke.
- `scnet_large_ds_flash` and `scnet_large_ds_pro` require Windows local proxy `4505`; it is running and OpenAI-compatible locally.
- `cf_kimi_k26` works but failed strict JSON/code-only fixtures, so it is fallback capacity.
- `kimi`, `kimi_thinking`, and `kimi_search` require Windows local proxy `4504`; the port is running, but current chat calls fail with Kimi anonymous quota/login-state exhaustion.
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

Latest SCNet first-tier deployment:

- Backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Local tests: `71 passed in 0.59s`.
- VPS route order: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o`.
- Public coding smoke: 200 in 3347ms.

Latest documentation/FRP verification:

- `git diff --check` passed with line-ending warnings only.
- Core suite passed with `pytest --ignore=active_model`: `66 passed, 5 skipped`.
- Plain pytest collection currently fails because `D:\GIT\active_model` is a stale junction to `C:\Users\Administrator\AppData\Local\Temp\tmpejcswwyo\fake_adapter`.
- Public FRP smoke passed:
  - `http://47.112.162.80:8088/health`: 200.
  - `http://47.112.162.80:8088/v1/models`: 200.
  - `http://47.112.162.80:8088/v1/chat/completions`: 200.

## Current Risks

- Some registered backends require Windows local proxy services, so VPS `localhost` is not a valid health signal for them.
- Kimi free models are not all usable yet; CF Kimi is reachable, while local Kimi needs session re-login.
- SCNet direct models passed the first production VPS coding fixture set; keep monitoring real IDE latency and fallback quality.
- Free web AI expansion can add capacity, but candidates must stay sandboxed until rate limits, auth state, and failure classes are understood.
- The repo contains many local reference directories and temporary scripts; do not stage them blindly.
- `server.py` is still large and should be split later, but not during routing experiments.

## Next Phase

User asked to finish this documentation/GitHub upload first, then wait for the next instruction.

Prepared next-phase priorities:

1. Find more no-login web AI candidates, starting with Duck.ai and HeckAI-like sources.
2. Improve backend stability with token/session refresh detection, quota handling, and rate-limit cooldown.
3. Optimize routing so free backends are used efficiently by task fit, remaining quota, latency, and quality.

Implementation started after user said to continue:

- Created branch `codex/free-web-ai-probe`.
- Added `data/free_web_ai_candidates.json`.
- Added `docs/free-web-ai-candidates.md`.
- Added `scripts/probe_free_web_ai.py`.
- Added `tests/test_free_web_ai_probe.py`.
- Probe command found all six candidate pages reachable with HTTP 200, but this is not yet model admission.
- Added backend failure classes in `health_tracker.py`: `manual_refresh_required`, `quota_exhausted`, `rate_limited`, `auth_expired`, `timeout`, `provider_error`, `unknown_error`.
- `http_caller.py` now passes error text into `health_tracker.record_failure`, so Kimi anonymous quota errors can be classified instead of retried blindly.
- Verification after this increment:
  - `pytest --ignore=active_model`: `72 passed, 5 skipped`.
  - `json.tool` passed for `data/free_web_ai_candidates.json` and `data/free_web_ai_probe_results.json`.
  - `scripts/probe_free_web_ai.py --dry-run` listed six candidates.
  - `http://47.112.162.80:8088/health` returned 200.

Next implementation item:

- Task 4 quota-aware routing, after current branch is verified and committed.

## 2026-05-22 Local Reverse AI Inventory

User corrected the earlier assumption that Duck.ai still needed reverse engineering. Local audit confirmed:

- `D:\duckai` is an existing DuckAI OpenAI-compatible reverse bridge.
- Port `4500` is listening with `bun run src/server.ts`.
- DuckAI `/v1/models` exposes `gpt-4o-mini`, `gpt-5-mini`, `claude-haiku-4-5`, `meta-llama/Llama-4-Scout-17B-16E-Instruct`, `mistral-small-2603`, and `tinfoil/gpt-oss-120b`.
- DuckAI user-only chat returns HTTP 200 locally.
- DuckAI fails when LiMa/OpenAI format includes an empty `system` message; current `http_caller.py` prepends that message for every OpenAI backend.
- `ddg.zhuguang.ccwu.cc` currently returns Cloudflare 1033, so the public tunnel is not healthy.

Other local reverse/proxy state:

- `4505` SCNet-large is running and chat-compatible.
- `4504` Kimi is running and exposes models, but chat returns `chat.anonymous_usage_exceeded`.
- `4502` TheOldLLM exposes models, but local chat timed out in the latest smoke.
- `4503` g4f wrapper is running; default chat works, but provider/model mapping is fragile.
- `D:\ollama_server\heckai-worker.js` exists, so HeckAI is an adapter-draft task, not a blank reverse task.
- HIX Chat, GPT.chat, Deep-seek mirror, and PLAI.chat are still page-only candidates.

New source-of-truth docs:

- `docs/LOCAL_REVERSE_AI_STATUS.md`
- `data/local_reverse_ai_inventory.json`
- `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md`

## 2026-05-22 DuckAI And SCNet-Large Admission Increment

Implemented after the local reverse inventory:

- `http_caller._build_body` now honors `no_system` for OpenAI backends. It omits the synthetic system role and merges non-empty system/IDE context into the first user message.
- Existing DuckAI backends are marked `no_system`.
- DuckAI registrations now include `ddg_gpt5_mini`, `ddg_claude_haiku_45`, and `ddg_tinfoil_gptoss_120b`.
- Router pools keep DuckAI at late fallback only; it is not promoted over SCNet first-tier backends.

Local DuckAI three-case coding admission with `DDG_TUNNEL_URL=http://localhost:4500`:

- `ddg_gpt4o_mini`: 3/3, avg score 100, avg latency 3022ms.
- `ddg_gpt5_mini`: 3/3, avg score 100, avg latency 3626ms.
- `ddg_claude_haiku_45`: 2/3, failed strict JSON tool-output fixture.
- `ddg_tinfoil_gptoss_120b`: failed with upstream 500 then cooldown.

SCNet-large local route eval:

- `scnet_large_ds_flash`: 3/3, avg score 100, avg latency 987ms.
- `scnet_large_ds_pro`: 3/3, avg score 100, avg latency 3899ms.
- This makes SCNet-large a strong Windows-local/FRP candidate, but a topology guard is required before any VPS-first promotion because VPS `localhost:4505` is not the Windows proxy.

Kimi and TheOldLLM guardrails:

- Kimi still returns `chat.anonymous_usage_exceeded`; `health_tracker` maps it to `manual_refresh_required`.
- The current Kimi/TheOldLLM refresh/log path can expose token fragments, so redact that output before active refresh runs.
- TheOldLLM local `4502` chat still timed out after 30 seconds in this pass.

## 2026-05-22 Cloudflare Workers AI Routing Increment

User asked whether the Cloudflare dashboard models are used and then approved implementation.

What changed:

- Added `docs/CLOUDFLARE_MODEL_INVENTORY.md`.
- Added `cfai_mistral` for Worker model `mistral-small-3.1`.
- Added Cloudflare code-capable backends to `router_v3.py` and `code_orchestrator.py`.
- Raised `router_v3.MAX_FALLBACKS` from 5 to 8 because a pool entry outside the selection window is not active capacity.
- Added route assertions in `test_routing_engine.py`.
- Generated `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md` and `data/cloudflare_worker_quick_eval.json`.

Verified facts:

- `https://ai.zhuguang.ccwu.cc/v1/models` returns `llama-3.3-70b`, `llama-4-scout`, `qwen2.5-coder-32b`, `deepseek-r1-32b`, and `mistral-small-3.1`.
- Worker completion with `qwen2.5-coder-32b` returned exactly `cfai-ok`.
- One-case coding eval:
  - `cfai_qwen_coder`: 1/1, 2166ms.
  - `cfai_deepseek_r1`: 1/1, 6919ms.
  - `cfai_mistral`: 0/1, HTTP 500 from Worker.
- `router_v3.select_backends("code", {})` now includes `cf_qwen_coder` and `cfai_qwen_coder` in the default selection window.
- Current shell has no `CLOUDFLARE_ACCOUNT_ID` or `CLOUDFLARE_TOKEN`, so direct account API smoke remains pending.

Verification commands:

- `D:\GIT\venv\Scripts\python.exe -m py_compile backends.py router_v3.py code_orchestrator.py test_routing_engine.py`
- `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py -q --ignore=active_model` -> `25 passed`.
- `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py tests\test_coding_eval.py tests\test_lima_context.py -q --ignore=active_model` -> `38 passed`.

Guardrail:

- Dashboard models that are embeddings, image, speech, rerank, or classification should not be added to chat routing. Add dedicated adapters first.

## 2026-05-22 Cloudflare Routing VPS Deployment

Deployed the Cloudflare routing increment to VPS after local verification.

Deployment details:

- Backup: `/opt/lima-router/backups/cloudflare-routing-20260522_210441`.
- Uploaded: `backends.py`, `router_v3.py`, `code_orchestrator.py`.
- Remote compile passed for `server.py`, `routing_engine.py`, `backends.py`, `router_v3.py`, and `code_orchestrator.py`.
- `lima-router` restarted successfully.
- VPS-local `/health` returned 200.

Post-deploy probes:

- `router_v3.select_backends("code", {})` on VPS returned:
  `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o`, `github_gpt4o_mini`, `cf_qwen_coder`, `cfai_qwen_coder`.
- VPS direct account Cloudflare smoke: `cf_qwen_coder` returned `cf-direct-ok`.
- VPS Worker Cloudflare smoke: `cfai_qwen_coder` returned `cfai-ok`.
- Public `https://chat.donglicao.com/v1/models` returned 200.
- Public `https://chat.donglicao.com/v1/chat/completions` returned 200 with backend `groq_gptoss_20b` in 601ms.
- FRP `http://47.112.162.80:8088/health` still returned 200.

Rollback:

```bash
cd /opt/lima-router
cp -p backups/cloudflare-routing-20260522_210441/backends.py .
cp -p backups/cloudflare-routing-20260522_210441/router_v3.py .
cp -p backups/cloudflare-routing-20260522_210441/code_orchestrator.py .
systemctl restart lima-router
```

## 2026-05-22 Token-Safe Local Proxy Routing Increment

Phase 15 started with two concrete root causes:

- Kimi/TheOldLLM local refresh helpers in `D:\ollama_server` printed or returned token material.
- Windows-only proxy backends depended on `localhost:4500/4504/4505` but routing had no explicit runtime topology guard.

Repo changes:

- Added `runtime_topology.py`.
- `router_v3.select_backends` now filters local-only backends through `runtime_topology.filter_backends`.
- `code_orchestrator._try_backends_ranked` filters its pool before trying candidates.
- Local-only backends stay available when a local port is reachable, an explicit tunnel URL override is set, or `LIMA_ENABLE_LOCAL_PROXIES` / `LIMA_RUNTIME_LOCAL_PROXIES` is truthy.

Local runtime changes under `D:\ollama_server`:

- Added `secret_redactor.js`.
- Removed hardcoded Cloudflare API token fallback from Kimi and TheOldLLM refresh scripts.
- Removed hardcoded TheOldLLM request token from `oldllm_proxy.js`.
- Replaced token/request-body/localStorage logging with redacted status logs.
- Changed `token_refresh_server.js` `/refresh` responses to report token presence instead of returning token values.

Guardrails:

- Refresh scripts were not run in this pass after redaction; a later manual refresh still needs suitable environment variables and login/session state.
- `D:\ollama_server` scripts are local runtime assets and were changed in-place, not committed to the LiMa repo.

Verification:

- `D:\GIT\venv\Scripts\python.exe -m py_compile runtime_topology.py router_v3.py code_orchestrator.py test_routing_engine.py`.
- `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py tests\test_coding_eval.py tests\test_lima_context.py -q --ignore=active_model` -> `70 passed`.
- `node --check` passed for the edited local JavaScript scripts.
- Redactor behavior check replaced Bearer, CF API, TheOldLLM request, and tenant token samples with `[REDACTED]`.

VPS deployment:

- Topology guard backup: `/opt/lima-router/backups/topology-guard-20260522_211850`.
- Short-answer hotfix backup: `/opt/lima-router/backups/short-answer-hotfix-20260522_212816`.
- Exact-output quality backup: `/opt/lima-router/backups/exact-output-quality-20260522_212959`.
- Uploaded `runtime_topology.py`, `router_v3.py`, `code_orchestrator.py`, and later `server.py`.
- Remote compile passed; `lima-router` restarted; `/health` returned 200.

Production issue found during verification:

- Public `https://chat.donglicao.com/v1/chat/completions` initially returned HTTP 200 with `system_fingerprint=router_fallback_exhausted` for `Return exactly: topology-ok`.
- Direct backend calls and `routing_engine.route` worked, so credentials and topology guard were not the root cause.
- Root cause was `server.py` quality gating: short exact answers under 30 chars were rejected when complexity was above `0.3`, and later long non-matching exact-output answers could pass by length alone.
- Fix: `_quality_check` now receives the user query, allows explicit short exact-output answers, and rejects non-matching answers when the expected direct answer can be parsed.

Final verification:

- Local compile passed for `server.py`, `runtime_topology.py`, `router_v3.py`, `code_orchestrator.py`, and `test_routing_engine.py`.
- Focused local suite returned `73 passed`.
- Public OpenAI-compatible smoke returned exact `topology-ok` with backend `longcat_chat`.
- Public Anthropic `/v1/messages` smoke returned exact `ide-ok`.
- FRP health `http://47.112.162.80:8088/health` returned 200.
