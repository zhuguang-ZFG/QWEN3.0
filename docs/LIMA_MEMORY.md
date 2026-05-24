# LiMa Memory

## 2026-05-25 Joint Debug Memory

- 2026-05-25 VPS baseline deploy updated `/opt/lima-router` to local `HEAD`
  `ad7cab5`. Backup:
  `/opt/lima-router/backups/codex-baseline-20260525_031146/runtime-before.tgz`.
  Remote compile, `lima-router` restart, local health, public online smoke
  `12/12`, authenticated worker preflight, and public fake U8 WSS loop all
  passed. Exact chat token: `baseline_ad7cab5_ok`.
- Three-project joint debug covered LiMa Server (`D:\GIT`), LiMa Code (`D:\GIT\deepcode-cli`), and ESP32/U8 tooling (`D:\GIT\esp32S_XYZ`).
- Root cause for local fake U8 WebSocket failure was a stale Windows router process on port `8080`; it did not load `routes.device_gateway`, so `/device/v1/health` returned `404`.
- After restarting the router from current `D:\GIT\server.py` and injecting a test `LIMA_DEVICE_TOKENS` entry for the spawned process, local fake U8 completed the full hello, heartbeat, motion task, and motion event acknowledgement loop.
- Public `https://chat.donglicao.com/device/v1/health` originally returned the chat HTML because nginx had no `/device/` location. The tracked VPS nginx snapshot now includes `/device/v1/ws` WebSocket proxying and `/device/` HTTP proxying to the router.
- Redis HA mode for Device Gateway is default-off. Enable with `LIMA_DEVICE_TASK_STORE=redis`, `LIMA_DEVICE_SESSION_BUS=redis`, and `LIMA_DEVICE_REDIS_URL`; this shares task queues and publishes task-available notifications so the process with the local WebSocket session can drain remote-created tasks.
- On 2026-05-25 VPS Redis HA was enabled for Device Gateway. Redis must remain loopback-only; public `6379` is part of online distribution guard checks.
- On 2026-05-25 LiMa Code Phase 7 first workflow slice advanced
  `deepcode-cli` to `03bd626`, adding local `/lima plan`,
  `/lima test [--cmd <command>]`, and `/lima ship` commands. These run through
  the guarded local task runner, write audit evidence, do not submit to Server,
  and were verified with `npm.cmd run check`, `npm.cmd test` (`430 passed, 6
  skipped`), and `git diff --check`.

> Updated: 2026-05-25
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

Online distribution control:

- The official website, open platform, chat interface, FRP path, nginx edge, and public service wiring belong to this LiMa repo.
- Source of truth: `docs/ONLINE_DISTRIBUTIONS.md`.
- Sanitized VPS config snapshots: `infra/vps/nginx/` and `infra/vps/systemd/`.
- Public smoke command: `python scripts/smoke_online_distributions.py`.
- VPS systemd units must not contain provider keys or tokens; secrets belong in root-readable env files.

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
| `mastery_loop/` | Evidence-backed module mastery, weak-point extraction, review scheduling, and recommendations. |
| `agent_evolution/` | Candidate skill extraction plus gated promotion requiring eval, manual approval, and mastery evidence. |

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
- `/opt/lima-router/backups/mastery-loop-20260524-125511`

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

Latest mastery-loop deployment:

- Runtime commit: `bd0bf04` (`feat: add mastery loop evidence gates`).
- Remote `py_compile` and import smoke passed for `mastery_loop`, `agent_evolution`, and `routes.agent_tasks`.
- VPS `/health`: 200 with `agent_tasks=true`.
- Public HTTPS chat returned exact `mastery_loop_https_ok`.
- Public FRP chat returned exact `mastery_loop_frp_ok`.
- Worker preflight returned `ready=true`, `contract_version=agent-task-v1`.

Latest online-distribution governance update:

- Added `docs/ONLINE_DISTRIBUTIONS.md`.
- Added sanitized nginx snapshots for `chat.donglicao.com`, `api.donglicao.com`, and `www.donglicao.com`.
- Added sanitized systemd snapshots for `lima-router.service` and `lima-voice.service`.
- Added `scripts/smoke_online_distributions.py`.
- Migrated provider-key-like environment lines out of VPS systemd unit files into root-readable env files.
- Moved service-unit secret migration backups to `/root/secure-service-backups` with mode `600`.
- Historical `python scripts/smoke_online_distributions.py --chat-exact distribution_control_ok` passed `10/10`; latest online distribution smoke is `12/12` after Device Gateway Redis HA and public `6379` guard.

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

## 2026-05-23 Codebase Calibration

Latest local status check:

- Branch: `codex/free-web-ai-probe`.
- Latest checked commit: `8b86228`.
- LiMa target-suite verification: `382 passed, 8 skipped`.
- Do not describe this as unrestricted full-repo pytest; this workspace contains many unrelated local reference repositories and generated trees.

Current integration truth:

- Session Memory is now in the successful chat path as SQLite write.
- Prompt-time Session Memory recall is now a first-class `server.py` stage: `session_memory.prompt_recall.apply_prompt_memory_recall()` runs before token budget checks, identity adaptation, routing analysis, non-streaming `v3_route`, OpenAI streaming, and fallback retry messages.
- Recall evidence is intentionally metadata-only: OpenAI-compatible responses include `x_lima_meta.memory_recall`, and request traces include a `prompt_memory_recall` span without leaking recalled memory content.
- `server.py` lifespan starts `session_memory.daemon`, so inbox ingestion and consolidation can run outside `/v1/chat/completions`.
- `scripts/memory_daemon_ctl.py status|run-once` provides a local ops entry point for checking daemon config and running one safe cycle.
- Graph retrieval and reranking are injected through the shared `inject_retrieval_context()` path with trace evidence.
- `context_pipeline.factory.build_default_pipeline()` is tested, but `server.py` still uses explicit integration blocks.
- Tool Gateway has been hardened with `shell=False`, simple safe-argument validation, copied HTTP args, and audit events.
- Admin UI API calls use bearer auth and safe JS token escaping; query-token login remains a later hardening target.
- `key_pool.py` is wired into `http_caller.py` for provider key scheduling and exposes redacted telemetry; `ConcurrencyPool` remains a separate tested primitive rather than replacing key scheduling.

Reference project conclusions:

- OpenRAG is a good reference for ingestion, retrieval traceability, MCP knowledge tools, and mature document parsing. It should not replace LiMa's router or be copied wholesale.
- Google Cloud always-on-memory-agent is a stronger reference for LiMa's next memory step: background inbox ingestion, typed memories, consolidation, and source-backed recall.
- TechSpar is now borrowed as a local mastery loop, not a runtime dependency: `mastery_loop/` records mastery events, weak points, review schedules, and recommendations without changing hot-path routing.
- New detailed reference evaluation: `docs/REFERENCE_PROJECT_EVALUATION.md`.

Current architecture closure:

1. Graph/code retrieval prompt injection and trace evidence are implemented.
2. Typed memory daemon, prompt-time recall, and MCP memory/retrieval tools are implemented.
3. Backend config, `key_pool.py` integration, endpoint extraction, and the TechSpar-inspired mastery loop are implemented.
4. Remaining non-closed items are policy-gated rather than missing implementation: always-on worker daemon, Kimi/TheOldLLM/MiMo/page-only candidate promotion, and refresh execution.

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

## 2026-05-24 VPS + FRP + LiMa Code Worker Closure

The main LiMa Server and `D:\GIT\deepcode-cli` now have a public end-to-end worker smoke on the deployed VPS path.

Deployment evidence:

- Main branch in use: `codex/free-web-ai-probe`.
- Latest deployed runtime commit after chat request helper extraction: `4e7d4a7` (`refactor: extract chat request helpers`).
- VPS runtime backups:
  - `/opt/lima-router/backups/agent-worker-sync-20260524_104836`
  - `/opt/lima-router/backups/runtime-deps-sync-20260524_105115`
  - `/opt/lima-router/backups/lifespan-extract-20260524_111647`
  - `/opt/lima-router/backups/chat-models-extract-20260524_113220`
  - `/opt/lima-router/backups/chat-request-utils-20260524_114403`
- Remote compile and `import server; import chat_models; import chat_request_utils` passed before restart.
- `systemctl restart lima-router` completed; VPS-local `/health` reports `modules.mcp=true`, `modules.agent_tasks=true`, and `modules.telegram=true`.
- `chat_models.py` now owns `Message`, `ChatRequest`, and `extract_system_prompt`; `server.py` imports and re-exports them for existing tests and callers.
- `chat_request_utils.py` now owns shared request-body helpers for extracting system prompt previews and last user text from OpenAI/Anthropic-shaped messages.

Public smoke evidence:

- HTTPS chat: `https://chat.donglicao.com/v1/chat/completions` returned exact `lima-postdeploy-ok`.
- HTTPS chat after lifespan extraction: `https://chat.donglicao.com/v1/chat/completions` returned exact `lima-lifespan-deploy-ok`.
- HTTPS chat after chat model extraction: `https://chat.donglicao.com/v1/chat/completions` returned exact `deploy_https_ok_1134`.
- HTTPS chat after chat request helper extraction: `https://chat.donglicao.com/v1/chat/completions` returned exact `request_utils_https_ok`.
- Worker preflight: `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`, and `smoke_task=true`.
- Worker preflight after chat model extraction returned `ready=true`, latest task `cfcd3f2b`.
- Real-machine worker task:
  - Server task id: `cfcd3f2b`.
  - LiMa Code command: `/lima task cfcd3f2b`.
  - Result: `needs_review`, summary `No git diff found to review.`
  - Server events: `created,result_submitted`.

FRP/local-router closure:

- Temporary FRP chat failure was not a tunnel failure. It was the Windows local router process on `127.0.0.1:8080` running without private API key environment after manual restart.
- `D:\ollama_server\start-lima-api.ps1` now ensures `LIMA_API_KEY` and `LIMA_API_KEYS` are present for the child router process without logging key values.
- Tracked `local_router_start.bat` now defaults the local private key to `lima-local` when neither `LIMA_API_KEY` nor `LIMA_API_KEYS` is already configured.
- Final smokes:
  - `http://127.0.0.1:8080/v1/chat/completions` returned exact `lima-final-local-ok`.
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-final-frp-ok`.
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-lifespan-frp-ok` after the lifespan extraction deployment.
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-chat-models-frp-ok` after the chat model extraction deployment.
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `request_utils_frp_ok` after the chat request helper extraction deployment.
  - Process state: one Windows `server.py` router process and one `frpc.exe` process.

Known remaining gated items after this closure:

1. Keep Kimi local, TheOldLLM, MiMo web, and page-only web AI candidates gated until refresh plus model-level smoke evidence exists.
2. Keep always-on worker daemon mode behind explicit repo allowlist, runtime budget, stop marker, audit, failure quarantine, and manual production gates.
3. Keep mastery-loop admin exposure and any hot-path planner/routing influence behind private admin guards and follow-up tests.

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

## 2026-05-22 Open Phase Completion

Closed the final three `task_plan.md` in-progress phases.

IDE/agent verification:

- `docs/IDE_AGENT_VERIFICATION.md` is the durable verification record.
- Public OpenAI-compatible IDE smoke returned exact `phase-complete-ok` with backend `scnet_ds_flash`.
- Public Anthropic-compatible `/v1/messages` smoke returned exact `ide-agent-complete`.
- Real Claude Code CLI command returned exact `claude-cli-ok`:

```powershell
$env:ANTHROPIC_API_KEY='lima-local'
$env:ANTHROPIC_BASE_URL='https://chat.donglicao.com'
claude --bare --model lima-1.3 --max-budget-usd 5 -p "Return exactly: claude-cli-ok"
```

Free web AI admission:

- Candidate registry now includes DuckAI, HeckAI, HIX, GPT.chat, DeepSeek mirrors, PLAI, GLM-AI, InstantSeek, and chat-gpt.org.
- Harmless probe output: `data/free_web_ai_probe_results.json`.
- Admission output: `data/free_web_ai_admission.json` and `docs/FREE_WEB_AI_ADMISSION.md`.
- DuckAI is admitted only as a late fallback from existing local reverse + coding admission evidence.
- HeckAI stays `adapter_draft_pending`.
- Page-only candidates stay `sandbox_only`; private code remains disabled.

Stability and routing optimization:

- Added `route_scorer.py` with effective score:
  - quality 45%;
  - stability 25%;
  - latency 15%;
  - remaining quota 10%;
  - task fit 5%.
- `routing_engine.select()` now filters exhausted budget, cooled-down backends, terminal auth/quota/manual-refresh states, and unproven web adapters for IDE routes.
- `budget_manager.py` exposes `get_remaining_quota_score()`.

Deployment:

- VPS backup: `/opt/lima-router/backups/complete-open-phases-20260522_214621`.
- Uploaded `route_scorer.py`, `routing_engine.py`, and `budget_manager.py`.
- Remote compile passed, `lima-router` restarted, and VPS-local `/health` returned 200.

Verification:

- Local compile passed for touched runtime/test files.
- Focused suite returned `86 passed`.
- Public OpenAI-compatible smoke, Anthropic-compatible smoke, Claude Code CLI smoke, and FRP health all passed.

## 2026-05-22 Claude Code Tool Protocol Hardening

User-reported symptom:

- Claude Code connected to LiMa completed a local `Read` tool, then failed the next API turn with `API returned an empty or malformed response (HTTP 200)`.
- Repeating `继续` hit the same error in the same Claude Code session.

Diagnosis:

- Basic public `/v1/messages` and simple Claude CLI requests were healthy.
- Minimal real Claude Code `Read D:\GIT\routing_engine.py` tool loop passed.
- Large real Claude Code `Read D:\GIT\server.py` tool loop also passed before the fix, so this was not a total tool-protocol outage.
- The uncovered root-cause class was upstream response shape drift: a free OpenAI-compatible tool backend can return HTTP 200 with empty or malformed `choices[0].message`; the old converter could produce Anthropic HTTP 200 with an empty `content` array.

Fix:

- Added `tests/test_anthropic_tool_protocol.py` to cover:
  - empty OpenAI assistant message;
  - malformed `choices`;
  - list-style text content normalization;
  - streaming `tool_use` start block shape.
- Updated `server.py` so `_convert_response_openai_to_anthropic()` always returns a valid Anthropic message with at least one content block.
- Preserved valid OpenAI `tool_calls` as Anthropic `tool_use`.
- Added `input: {}` to simulated Anthropic SSE `tool_use` content block starts.
- Updated `docs/CLAUDE_CODE_TOOL_ROUTING.md` with the failure mode and verification plan.

Verification:

- RED: new protocol tests initially failed 4/4 against the old conversion behavior.
- GREEN: `tests/test_anthropic_tool_protocol.py` passed 4/4.
- Local compile: `D:\GIT\venv\Scripts\python.exe -m py_compile server.py`.
- Focused suite: `90 passed, 5 skipped`.
- VPS backup: `/opt/lima-router/backups/claude-tool-protocol-20260522_220037`.
- VPS remote compile passed; `lima-router` restarted active; VPS-local `/health` returned 200.
- Public `/v1/messages` smoke returned exact `deployed-msg-ok`.
- Real Claude Code CLI large-file tool loop returned exact `deployed-read-ok`.
- FRP `http://47.112.162.80:8088/health` returned 200.

Operational lesson:

- If Claude Code reports malformed HTTP 200 after a tool result, inspect the Anthropic conversion boundary before assuming FRP, nginx, or Claude CLI config is broken.

## 2026-05-22 Local P0 Router Hardening And Plan Closure

This increment was first closed locally, then deployed to VPS after explicit user approval.

P0 hardening changes:

- Added `access_guard.py` to enforce private API access through `LIMA_API_KEY` and comma-separated `LIMA_API_KEYS`.
- Protected local `/v1/chat/completions`, `/v1/messages`, `/api/live-key`, `/v1/status`, and `/v1/images/generations`.
- Kept `/health` and `/v1/models` public for uptime checks and IDE model discovery.
- Changed admin routes to fail closed with 503 when `LIMA_ADMIN_TOKEN` is not configured.
- Preserved full multi-turn `messages` during fallback backend retries by extending `_try_backend()`.
- Changed ordinary chat IDE detection to return an empty string instead of a truthy unknown marker.
- Capped image generation dimensions at `2048x2048`.
- Removed client-visible Anthropic streaming backend footers like `[LiMa -> backend]`; backend selection stays internal request evidence only.
- Reworked `test_streaming.py` so async generator checks run through `asyncio.run()` instead of being skipped without `pytest-asyncio`.

Verification:

- `D:\GIT\venv\Scripts\python.exe -m py_compile access_guard.py server.py routes\admin.py` passed.
- `tests/test_access_guard.py` and `tests/test_fallback_context.py`: `6 passed`.
- `tests/test_ide_detection.py` and `tests/test_image_endpoint_guard.py`: `4 passed`.
- `tests/test_stream_footer.py`: `2 passed`.
- `test_streaming.py`: `5 passed`.
- Core regression suite with P0 tests: `112 passed`.

VPS deployment:

- GitHub push: commit `c4515d3` on branch `codex/free-web-ai-probe`.
- P0 runtime backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
- Uploaded runtime files: `server.py`, `access_guard.py`, and `routes/admin.py`.
- Remote `.env` backup is inside the P0 backup directory; `LIMA_API_KEY` was added because neither `LIMA_API_KEY` nor `LIMA_API_KEYS` was configured and the new guard fails closed.
- Remote compile passed for `server.py`, `access_guard.py`, and `routes/admin.py`.
- `lima-router` restarted and became active.
- First smoke immediately after restart hit a transient `Connection refused` before uvicorn was listening; follow-up status showed the service active and listening on `0.0.0.0:8080`.
- Public no-auth `/v1/chat/completions` returned 401 as expected.

Deployment follow-up fix:

- Public authorized `/v1/chat/completions` and `/v1/messages` initially returned 500.
- Root cause: VPS had a stale `health_tracker.py`; `routing_engine.py` called `health_tracker.get_backend_state()`, but the remote module did not have that function.
- Health tracker sync backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
- Uploaded `health_tracker.py`, remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`, then restarted `lima-router`.
- Public authorized `/v1/chat/completions` returned exact `p0-deploy-ok` with backend `router_longcat_chat`.
- Public authorized `/v1/messages` returned exact `p0-msg-ok` with `stop_reason=end_turn`.
- FRP `http://47.112.162.80:8088/health` still returned 200.

Plan closure整理:

- Added `docs/superpowers/PLAN_CLOSURE_STATUS.md`.
- Reconciled historical Superpowers plan checkboxes:
  - `2026-05-22-cloudflare-workers-ai-routing.md`
  - `2026-05-22-token-safe-local-proxy-routing.md`
  - `2026-05-22-free-model-first-tier-eval.md`
- All real task checkboxes in `docs/superpowers/plans/*.md` are now reconciled. Remaining literal `- [ ]` matches are boilerplate syntax examples.
- Main `task_plan.md` phases are complete.
- Current P0 hardening is now production closed after the explicit VPS deployment pass.

Deferred risks and non-goals:

- Kimi local proxy still returns `chat.anonymous_usage_exceeded` and remains `manual_refresh_required`.
- TheOldLLM local proxy still times out on chat.
- Page-only no-login web AI candidates remain sandbox-only.
- Local refresh scripts under `D:\ollama_server` were redacted and syntax-checked, but refresh execution itself remains deferred.

## 2026-05-23 Code Quality Hardening Closure

The code-quality report was treated as candidate audit input, not as a source of truth. This round accepted only items that were rechecked and fixed locally:

- `smart_router._has_vision_content` had been called from the `cf_vision` path without a live helper. The image route now delegates to the existing vision detector, and `tests/test_vision_routing.py` protects the network/circuit-breaker boundary.
- Anthropic vision request stats now use the real request start time. `tests/test_request_stats.py` covers the helper and the `/v1/messages` image branch, preventing a future `0` duration write.
- `_record_request()` no longer performs IP location lookup while holding `_stats_lock`; only the stats update remains locked.
- Local one-off deploy/debug/run/stress probes are root-ignored, and tracked `scripts/` files no longer contain hardcoded `sk-` token literals.

Rejected or outdated report findings:

- Admin API routes are guarded after P0 hardening; the HTML admin shell is a separate surface.
- Current `deploy_v3.py` does not contain a plaintext deploy password; it reads `LIMA_DEPLOY_PASS` or uses a key path.
- The old `test_streaming.py` issue is stale because P0 made those checks run and pass.

Deferred architecture work:

- Split `server.py`.
- Make `BACKENDS` single-source.
- Deduplicate response-builder logic.
- Migrate `smart_router.cb_*` state into `health_tracker`.

Security and deployment notes:

- Any previously exposed tokens should be rotated; token values must never be copied into docs, commits, or chat.
- This closure was local-only. Do not deploy this round unless the user explicitly asks for a later deployment.

Verification evidence:

- `git -C D:\GIT diff --check`: no whitespace errors; emitted CRLF warnings for unrelated dirty tracked files.
- `D:\GIT\venv\Scripts\python.exe -m py_compile smart_router.py server.py`: passed.
- `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model`: `5 passed`.
- Core suite: `117 passed`.
- `git -C D:\GIT grep -n "sk-" -- scripts`: no output, expected exit 1 for no matches.

Follow-up security correction:

- A final whole-round review found the first tracked-script scrub was too narrow because it only checked `sk-` token shapes.
- Commit `e231a5e` removed the remaining tracked OneAPI/admin/provider credential literals from `scripts/*.py` and replaced them with environment-variable reads.
- Final sanitized checks found no tracked script hardcoded credential literals, and `D:\GIT\venv\Scripts\python.exe -m compileall -q scripts` passed.
- Treat any credentials that existed in repository history as exposed and rotate them. Never paste token values into docs, commits, or chat.

## 2026-05-23 LiMa Code Worker Command Runner

LiMa Code now has a real local command runner for the Server task path:

- `/lima connect` reports whether Server URL/API key configuration exists without printing the key.
- `/lima status` reports local project and Server configuration state.
- `/lima review` runs guarded local review mode over the current git diff.
- `/lima task <task_id>` fetches a protected LiMa Server task, runs the guarded local task runner, writes local audit evidence, and submits the structured result back to Server.
- `/lima next` claims one pending `accepted` LiMa Server task, runs it locally, writes audit evidence, and submits the structured result back to Server.
- `/lima work --once` and `/lima work --loop --max-tasks <n>` provide bounded worker execution; loop mode rejects unbounded runs.

Important boundary:

- Server still does not execute shell commands.
- LiMa Code executes only inside the guarded local workspace.
- `plan` and `review` are read-only.
- `patch` requires explicit `patch_files` and `write`.
- `test` requires explicit test commands and the `test` tool.
- Local audit output lives under `.lima-code/audit.jsonl`; `.lima-code/` is ignored by Git because it may contain local runtime state or credentials.

Evidence:

- Added `D:\GIT\deepcode-cli\src\lima\command-runner.ts`.
- Added `D:\GIT\deepcode-cli\src\tests\lima-command-runner.test.ts`.
- Wired `D:\GIT\deepcode-cli\src\ui\PromptInput.tsx` and `D:\GIT\deepcode-cli\src\ui\App.tsx` so `/lima task <id>` is handled locally instead of going to chat.
- Fixed Windows Bash timeout cleanup in `D:\GIT\deepcode-cli\src\tools\bash-handler.ts`; timeout now waits for process close after killing the process tree and ignores post-timeout output.
- Public end-to-end smoke:
  - Created Server task `4d6c02b3`.
  - Ran LiMa Code `/lima task 4d6c02b3` against `https://chat.donglicao.com`.
  - Worker submitted `needs_review` with changed files `src/ui/App.tsx` and `src/ui/PromptInput.tsx`.
  - Server detail confirmed `hasResult=true`; events endpoint returned `created,result_submitted`.
- Verification:
  - LiMa targeted tests: `41 passed`.
  - Tool handler tests: `22 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `368 passed, 7 skipped`.

Single-claim follow-up:

- Added `/lima next` as a one-task worker command.
- It intentionally claims only one task per run; do not turn it into a daemon without explicit backoff, stop, and audit controls.
- Public smoke created Server task `eb9410e1`, ran `/lima next`, submitted `needs_review`, and confirmed Server events `created,result_submitted`.
- Verification after this slice:
  - Parser/runner tests: `13 passed`.
  - LiMa worker targeted tests: `52 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `371 passed, 7 skipped`.

Bounded-loop follow-up:

- Added `/lima work --once` and `/lima work --loop --max-tasks <n>`.
- Loop mode requires `--max-tasks`, caps it at 100, and stops on no pending task, max count, failure, or UI abort.
- UI Ctrl+C/Esc now aborts active LiMa worker commands with an `AbortController`.
- Public smoke used a temporary empty directory to avoid sending local repository diff content:
  - Server tasks `3428f2b5` and `ae549d08`.
  - `/lima work --loop --max-tasks 2 --interval-ms 1`.
  - Both results were `needs_review`.
  - Both event streams returned `created,result_submitted`.
  - `changedFileCount=0`.
- Verification:
  - Parser/runner tests: `19 passed`.
  - LiMa worker targeted tests: `58 passed`.
  - `npm.cmd run check`: passed.
  - Full LiMa Code suite: `377 passed, 7 skipped`.

## 2026-05-23 Autonomous Worker v0.2 Design Direction

LiMa should continue toward the GenericAgent/Evolver/agency-agents direction, but as controlled autonomy rather than unconstrained self-evolution.

- GenericAgent-style skill growth maps to inactive candidate skills extracted from repeated successful coding tasks.
- Evolver-style evolution maps to evidence-gated promotion with regression tests and manual approval.
- agency-agents-style role decomposition maps to a compact coding role set, not a large simulated company.
- Server remains the orchestrator, lifecycle gate, and audit source.
- LiMa Code remains the local executor and may touch only allowlisted repositories.
- Before real daemon mode, implement stop control, claim leases, cancellation/control polling, repo allowlist, worker budgets, failure quarantine, audit viewing, and a safe real-repo patch/test smoke.

Plan document:

- `docs/superpowers/plans/2026-05-23-lima-autonomous-worker-v02.md`

## 2026-05-23 Autonomous Worker v0.2 Task 8

LiMa Code patch mode now supports the real patch-plus-test worker path locally:

- A task may carry explicit `patch_files` and `test_commands`.
- Patch mode applies only explicit files inside the guarded repo.
- If `test_commands` are present, the task must also allow the `test` tool.
- Results include changed files, diff preview, test commands, and test results.

Important contract decision:

- Server `AgentTaskRequest` and `/agent/tasks` now preserve `patch_files` and `test_commands`.
- LiMa Code validation also preserves those fields, so fetched Server tasks can drive real patch/test execution.
- This keeps Server as policy/audit broker only; Server still does not execute shell or mutate repositories.

Evidence:

- Server task contract and route tests: `31 passed`.
- LiMa Code worker tests: `407 passed, 6 skipped`.
- LiMa Code `npm.cmd run check`: passed.
- VPS public smoke remains pending until this Server contract is deployed and verified against a temporary repo.

## 2026-05-23 LiMa Server Control Plane v0.3

LiMa Server remains the orchestrator and audit source. This phase added:

- durable agent task audit summaries,
- a minimal admin audit view,
- Telegram approval callback parsing and review helper alignment,
- inactive candidate-skill creation from approved task evidence,
- a dry-run Server/Worker contract smoke script.

Boundary preserved: Server does not execute shell commands, does not auto-deploy, and does not auto-promote skills without eval evidence and manual approval.

## 2026-05-23 LiMa Real-Machine Worker Smoke v0.4

LiMa Server v0.4 should make real-machine worker testing repeatable:

- `/agent/worker/preflight` reports Server task-control readiness without secrets.
- `/agent/worker/smoke-task` creates bounded read-only or disposable patch smoke tasks.
- `scripts/create_lima_smoke_task.py` creates smoke tasks and prints the exact LiMa Code commands to run.
- `docs/LIMA_REAL_MACHINE_SMOKE.md` is the runbook.

Boundary preserved: Server still never executes shell, never mutates repositories, and never auto-deploys.

## 2026-05-23 Web-Reverse Model Admission

LiMa now has a dedicated safe admission batch for web-reverse/local-proxy models:

- Plan: `docs/superpowers/plans/2026-05-23-web-reverse-model-admission.md`.
- Tooling: `web_reverse_eval.py` and `scripts/eval_web_reverse_models.py`.
- Safety rule: synthetic public prompts only; no private code, local paths, secrets, or live user repository context.
- Broad smoke covered 29 registered web-reverse/local-proxy backends.
- Phase 2 eval conclusion:
  - `scnet_large_ds_flash` and `scnet_large_ds_pro` are `code_medium_candidate` from 3/3 passing fixtures.
  - `kimi`, `kimi_thinking`, and `kimi_search` are `code_floor_candidate`; they pass coding/review but fail strict JSON tool output.
  - `longcat_web` is `code_floor_candidate`; it passes coding/review but fails strict JSON tool output.
  - `longcat_web_research` is not a coding route candidate in the current fixture set.
  - DDG is currently blocked by HTTP 530.
  - OldLLM is currently blocked by HTTP 502.
  - MiMo web is currently blocked by expired local cookie/auth state.
- Evidence:
  - `docs/WEB_REVERSE_MODEL_SMOKE.md`
  - `docs/WEB_REVERSE_MODEL_EVAL.md`
  - `data/web_reverse_model_smoke.json`
  - `data/web_reverse_model_eval.json`

Routing decision: strong web-reverse models can be promoted based on these reports, but the eval tool itself never edits `router_v3.py` or promotes routes automatically.

Adapter fix:

- `http_caller._build_body()` supports `force_stream_param`.
- `longcat_web*` and `mimo_web*` send `stream:false` for non-stream calls, avoiding SSE-as-JSON parse failures.
- Web-proxy control messages are treated as backend errors, so expired cookies become auth/quota evidence instead of low-quality model answers.

## 2026-05-23 Global Code Quality Hardening

Plan executed locally: `docs/superpowers/plans/2026-05-23-global-code-quality-review-plan.md`.

Closed items:

- Admin auth no longer depends on import-time `LIMA_ADMIN_TOKEN` capture for current auth decisions.
- `routes/admin_auth.py` owns admin token/session verification.
- `routes/admin_agent_audit.py` owns the agent audit API.
- Active runtime secret literals in `backends.py`/local MiMo TTS path were removed or quarantined with tests.
- Web-reverse admission metadata now records which local web adapters are private-code allowed and which remain sandbox-only.
- `routing_engine.route()` uses shared retrieval injection.
- `server_context.py` owns prompt context staging and prompt-time memory recall setup.
- `routes.telegram.start_telegram_webhook()` is called from FastAPI lifespan instead of deprecated router `on_event`.
- `telegram_notify` now passes async callables into fire-and-forget scheduling, avoiding coroutine leaks in tests.

Verification:

- `compileall` over runtime, routes, tools, scripts, and tests passed.
- Full pytest passed: `391 passed, 8 skipped`.
- `git diff --check` passed with CRLF warnings only.

Deployment: not performed. Treat this as a local hardening closeout until a separate deployment plan is approved.

## 2026-05-23 Global Code Quality Follow-up P1

Follow-up plan: `docs/superpowers/plans/2026-05-23-global-code-quality-followup-p1.md`.

Closed deployment blockers:

- Prompt tests now assert the current LiMa chat identity wording instead of the older `技术顾问` label.
- `mimo_web`, `mimo_web_think`, and `mimo_web_flash` are removed from default `ide`/`chat` pools until cookie/auth blockers are resolved and a fresh synthetic eval justifies promotion.
- Core `routing_engine.route()` is guarded by regression coverage proving it does not import `fc_caller` for ordinary requests.
- `session_memory/prompt_recall.py` is tracked and covered by a repo manifest test.
- Identity filtering now applies to first-person model self-identification, not normal third-party facts.

Verification:

- Focused follow-up suite passed: `37 passed`.
- Compileall passed.
- Full pytest passed: `393 passed, 8 skipped`.

Deployment: not performed.

## 2026-05-23 LiMa Code Dev Search Tools v0.1

- LiMa Code dev-search tools are explicit, read-only, and MCP-exposed.
- Tools added: `dev_search_docs`, `dev_search_error`, `dev_read_url`, `dev_fetch_github_file`, `dev_summarize_sources`.
- External search input is redacted before transport: API-token patterns, Windows paths, and private IPs are removed.
- URL reads reject non-HTTP schemes and private/loopback targets.
- These tools are not part of default chat routing and must not send private repository contents to external search.
- Local verification: `compileall` passed; focused dev-search/tool/MCP suite returned `28 passed`; full pytest returned `405 passed, 8 skipped`.

## 2026-05-23 Dev Search Review Follow-up

- `search_gateway.safety.is_public_http_url()` now uses `ipaddress` parsing and blocks non-global IP literals, including IPv6 loopback, metadata/link-local addresses, and decimal/hex IPv4 loopback variants.
- The URL guard normalizes trailing-dot hostnames before hostname checks, so `localhost.` is blocked before TinyFish or dev-read fetches.
- Hostnames are resolved with `socket.getaddrinfo()` before fetch; every resolved address must be `ipaddress.ip_address(addr).is_global`, so loopback-resolving domains such as `localtest.me` are blocked.
- `search_gateway.tinyfish_transport._is_safe_url()` reuses the shared URL safety function instead of maintaining a second string-prefix guard.
- Dev-search intent detection covers common Chinese prompts such as `查一下`, `官方文档`, `怎么修`, `报错`, `读取`, and `打开链接`.
- MCP dev-search numeric arguments are bounded with defaults instead of surfacing raw `ValueError` strings.
- Telegram FC/TTS modules remain optional integrations, but `fc_caller.py`, `tool_dispatcher.py`, and `mimo_tts.py` are now tracked runtime files instead of local-only prototypes.
- Telegram FC/TTS is still outside ordinary routing. `GNEWS_API_KEY` and `MIMO_TTS_KEY` are environment-only; missing keys return stable local failures without opening network connections.
- Local verification: focused dev-search/MCP/TinyFish/Telegram suite returned `44 passed`; full pytest returned `411 passed, 8 skipped`.

## 2026-05-23 Telegram FC/TTS Repo Admission

- Plan and evidence: `docs/superpowers/plans/2026-05-23-telegram-fc-tts-repo-admission.md`.
- `mimo_tts.py` is no longer ignored by `.gitignore`.
- `tool_dispatcher.py` is now a small compatibility facade backed by focused `lima_fc_tools` modules.
- `lima_fc_tools` preserves the same 71 exported tool names while keeping tool schema text ASCII-only and each runtime file under 300 lines.
- The split information-tools module deduplicates tool schemas by function name and loads GNews credentials from `GNEWS_API_KEY`.
- `mimo_tts.tts()` checks `MIMO_TTS_KEY` at call time and returns `None` before constructing an HTTP client when missing.
- Secret hygiene now scans `fc_caller.py`, `tool_dispatcher.py`, `mimo_tts.py`, and `lima_fc_tools/*.py`.
- Clean split plan and evidence: `docs/superpowers/plans/2026-05-24-tool-dispatcher-clean-split.md`.
- Local verification: focused local-tool/security/Telegram suite returned `23 passed`; ruff passed for the split tool files; full pytest returned `418 passed, 8 skipped`.

## 2026-05-24 Backend Registry And Key-Pool Closure

- `backends.py` is now the shared source for backend capability/proxy sets:
  - `GFW_BACKENDS`;
  - `VISION_BACKENDS`;
  - `WEAK_BACKENDS`;
  - `CODE_CAPABLE_BACKENDS`;
  - `KEY_POOL_PREFIXES`.
- Shared helpers now cover capability checks, weak-backend checks, first backend lookup by capability, and key-pool provider inference.
- `smart_router.py` and `context_pipeline/reflection.py` no longer keep their own stale capability/proxy tables for the covered paths.
- `http_caller.py` now integrates with `key_pool.py`:
  - provider inferred from backend config or backend-name prefix;
  - pooled key selected for `call_api`, `call_raw`, and `call_api_stream`;
  - success/failure, including retry-after, reported back to the pool;
  - selected keys are passed into header construction without mutating backend config.
- `key_pool.py` supports env bootstrap through `LIMA_KEY_POOL_<PROVIDER>`, using comma, semicolon, or newline separated keys and optional weights such as `sk-a,sk-b:2`.
- Local verification passed:
  - focused registry/key-pool/reflection suite: `58 passed`;
  - expanded runtime regression: `110 passed`;
  - secret/request/vision/free-web admission suite: `10 passed`;
  - local `py_compile` passed for the changed runtime files plus `server.py`.
- VPS deployment:
  - runtime commit `659f484`;
  - backup `/opt/lima-router/backups/backend-registry-keypool-20260524-120642`;
  - remote `py_compile` and import smoke passed;
  - `lima-router` restarted active.
- Public smoke evidence:
  - `https://chat.donglicao.com/health` returned `status=ok`;
  - `https://chat.donglicao.com/v1/chat/completions` returned exact `backend_registry_https_ok`;
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `backend_registry_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 Endpoint And Key-Pool Telemetry Closure

- The active `server.py` decomposition plan is closed for the current architecture pass:
  - `routes/chat_endpoints.py` owns `/v1/chat/completions` and `/v1/messages`;
  - `routes/system_endpoints.py` owns `/v1/models`, `/health`, `/api/live-key`, and `/v1/status`;
  - `server.py` re-exports endpoint callables for compatibility while retaining core runtime orchestration.
- `key_pool.pool_snapshot()` provides operational telemetry without exposing raw provider keys:
  - hashed/suffix key IDs;
  - total, active, cooled, and blocked counts;
  - per-key weight, cooldown remaining seconds, and consecutive 429 count.
- Local verification:
  - endpoint/key-pool focused regression: `62 passed`;
  - expanded runtime/admission/security regression: `128 passed`;
  - local `py_compile` passed.
- VPS deployment:
  - runtime commit `d10ed57`;
  - backup `/opt/lima-router/backups/endpoints-keypool-closed-20260524-123145`;
  - remote `py_compile` and import smoke passed;
  - `lima-router` restarted active.
- Public smoke evidence:
  - `https://chat.donglicao.com/health` returned `status=ok`;
  - `https://chat.donglicao.com/v1/chat/completions` returned exact `endpoints_closed_https_ok`;
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `endpoints_closed_frp_ok`;
  - `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.

## 2026-05-24 LiMa Code Main-Repo Management Closure

- `deepcode-cli` is now a first-class main-repo managed component through a Git submodule.
- Submodule remote: `https://github.com/zhuguang-ZFG/deepcode-cli.git`.
- Pinned LiMa Code revision: `278a5f7` (`feat: add lima worker diagnostics`).
- `docs/LIMACODE_MANAGEMENT.md` records ownership boundaries:
  - LiMa Server owns routing, memory, backend health, task contracts, VPS deployment, and safety gates.
  - LiMa Code owns terminal coding workflow, local tool execution, MCP client behavior, worker loops, local audit files, and CLI behavior.
  - The main repo owns the pinned revision, integration records, cross-repo contract checks, and release/deploy evidence.
- Future LiMa Code changes should be committed and pushed in `deepcode-cli` first, then the main repo should advance only the submodule pointer plus related docs/tests.

## 2026-05-24 esp32S_XYZ Backend Management Closure

- `esp32S_XYZ` is now a first-class downstream LiMa product distribution through a Git submodule.
- Submodule remote: `https://github.com/zhuguang-ZFG/esp32S_XYZ.git`.
- Pinned product revision: `c6845e0` (`fix: exclude dead rymcu GitHub link from markdown check`).
- `docs/ESP32S_XYZ_MANAGEMENT.md` records the backend boundary:
  - LiMa owns AI/model routing, memory, safety policy, backend health, VPS endpoints, provider-key custody, and cross-repo compatibility evidence.
  - `esp32S_XYZ` owns firmware, Edge-A/B/C/D schemas, Xiaozhi/manager services, hardware validation, OTA/provisioning/self-check flows, monitoring, and fake-device tools.
  - Integration is contract-first; when chat/LLM, image/vector generation, voice/ASR/TTS, safety, OTA, telemetry, monitoring, or task orchestration changes across both repos, push the product repo first, then advance the main-repo submodule pointer and record verification.
- User explicitly authorized LiMa to clone/use the product repository and perform deep optimization or necessary refactoring inside `zhuguang-ZFG/esp32S_XYZ.git`.
- `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` records the execution order: reproduce baseline, map contracts, rank refactor targets, implement low-risk consolidation, add LiMa adapters where needed, then prepare hardware-gated release evidence.

## 2026-05-24 LiMa Direct Device Gateway Plan

- User selected the long-term clean architecture: modify U8 firmware so the device speaks a LiMa-native protocol directly, with no Xiaozhi server runtime dependency.
- Main architectural decision: add a LiMa Device Gateway route layer, not another model-routing layer.
- Planned first routes:
  - `/device/v1/ws` for U8 WebSocket sessions;
  - `/device/v1/health` for gateway readiness;
  - optional private `/device/v1/events` and `/device/v1/tasks` for fallback/test/debug paths.
- Model, ASR, TTS, image/vector, and LLM selection remain in the existing LiMa routing/provider stack.
- Source of truth: `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md`.
- First implementation slice should prove a text-only fake U8 loop before firmware or hardware changes: `hello`, `heartbeat`, transcript, deterministic `写你好` / `画一个星星`, bounded `motion_task`, and `motion_event` progress/done.

## 2026-05-24 Xiaozhi Server Deprecation Plan

- User agreed that Xiaozhi server can be retired, but not physically deleted until LiMa Direct Device Gateway reaches parity and hardware safety gates pass.
- Source of truth: `docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md`.
- Current policy:
  - mark `xiaozhi-server` as legacy migration reference first;
  - inventory each runtime responsibility and map it to a LiMa replacement or explicit rejection;
  - port deterministic intent, motion downlink, event uplink, device info, and self-check behavior;
  - quarantine or delete `xiaozhi-server` only after fake U8, U8 firmware direct mode, and real U8/U1 safety smoke are recorded.

## 2026-05-24 Voice Display Companion Hardware References

- User asked to include ElatoAI and the ESP32 TFT transparent-TV article in the future LiMa hardware route.
- Source of truth: `docs/reference/HARDWARE_COMPANION_REFERENCES.md`.
- Roadmap placement:
  - writing-machine direct control remains the first target;
  - ElatoAI is admitted as a voice AI / ESP32 companion-device reference for secure WebSocket-style sessions and realtime audio posture;
  - the ESP32 TFT transparent-TV build is admitted as a display / companion-screen reference for status, prompt, avatar, and ambient visual output;
  - neither reference is a current runtime dependency or a replacement for LiMa's deterministic task, safety, schema, telemetry, and fake-device gates.

## 2026-05-24 External Capability Radar

- User provided a broad reference list including Pyrefly, ml-intern, GitNexus, stash, ClawSweeper, Flipbook, TrendRadar, ElatoAI, PersonaPlex, CubeSandbox, browser-harness, Youdao Baoku, gbrain, rowboat, persona skill lists, code-review-graph, open-agents, WeClone, graphify, hindsight, Feynman, goclaw, gitreverse, PraisonAI, oh-my-codex, agency-agents, and OmniScientist.
- Source inventory: `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`.
- Adoption roadmap: `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`.
- Policy:
  - use these projects as capability references, not automatic dependencies;
  - no code copy from GPL, AGPL, missing-license, or unreviewed sources;
  - map each accepted idea to a LiMa-owned interface, tests, docs, and rollback path.
- First recommended adoption slice:
  - focused Pyrefly evaluation for stable Python modules;
  - code graph interface in `code_context`;
  - typed memory categories inspired by stash/hindsight;
  - browser verification route for online distributions;
  - defer agent-runtime and hardware-companion implementation until foundations are stable.
- PersonaPlex is admitted as a later realtime speech-to-speech persona and
  voice-conditioning reference. It must not become a runtime dependency without
  a model-license review, opt-in privacy policy, safety review, and resource
  budget.

## 2026-05-24 LiMa Device Gateway Implementation Slice

- Implemented the first LiMa Device Gateway code slice in the main repo:
  - `/device/v1/health`;
  - `/device/v1/ws`;
  - private `/device/v1/events`;
  - private `/device/v1/tasks`;
  - `hello`, `heartbeat`, stable protocol errors;
  - deterministic transcript mapping for `写你好` / `画一个星星`;
  - bounded fake `run_path` `motion_task`;
  - `motion_event` acknowledgement and in-memory task state.
- New modules:
  - `device_gateway/protocol.py`;
  - `device_gateway/auth.py`;
  - `device_gateway/sessions.py`;
  - `device_gateway/intent.py`;
  - `device_gateway/safety.py`;
  - `device_gateway/tasks.py`;
  - `routes/device_gateway.py`.
- Device auth uses `LIMA_DEVICE_TOKENS` in `device_id=token` format and stays
  separate from LiMa private/provider API keys.
- Verification passed:
  - `python -m py_compile server.py routes\device_gateway.py device_gateway\*.py`;
  - `pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py -q --ignore=active_model`: 15 passed;
  - `pytest tests\test_system_endpoints.py tests\test_chat_endpoints.py tests\test_agent_task_routes.py -q --ignore=active_model`: 31 passed.
- Remaining implementation gates:
  - U8 firmware direct client;
  - product-repo fake LiMa U8 client;
  - real U8/U1 safety smoke;
  - audio/TTS extension;
  - Xiaozhi runtime quarantine/removal after parity.

## 2026-05-24 esp32S_XYZ Fake LiMa U8 Client

- Product repo `D:\GIT\esp32S_XYZ` now includes a fake LiMa U8 client:
  - `tools/fake_lima_u8/app.py`;
  - `tools/fake_lima_u8/tests/test_app.py`.
- Product commit pushed to GitHub:
  - `78a62c9 test: add fake lima u8 client`.
- Main repo submodule pointer advanced to `78a62c9`.
- The fake client verifies the product-side script for:
  - `hello`;
  - `heartbeat`;
  - `transcript`;
  - expected `run_path` `motion_task`;
  - `motion_event` progress/done.
- Verification passed:
  - `python -m py_compile tools\fake_lima_u8\app.py`;
  - `python -m unittest tools.fake_lima_u8.tests.test_app -v`: 5 passed;
  - `python -m unittest tools.fake_device_server.tests.test_app tools.fake_ai.tests.test_app tools.fake_u1.tests.test_app -v`: 31 passed;
  - `python tools\validate_schemas.py`: `validated=62 passed=62 failed=0`.
- `.env.example` now documents `LIMA_DEVICE_TOKENS` for `/device/v1/ws` device auth.

## 2026-05-24 Device Gateway Concurrency

- The first Device Gateway implementation could be entered concurrently by
  FastAPI/WebSocket, but its internal in-memory session/task state did not yet
  have explicit concurrency guards or real offline queue semantics.
- Implemented concurrency support:
  - thread-safe session registry;
  - per-WebSocket-session async send lock;
  - thread-safe task store;
  - unique task ID generation under lock;
  - per-device pending task queues;
  - `/device/v1/tasks` queues offline tasks and sends immediately to online
    devices;
  - successful `hello` flushes pending tasks for that device only;
  - `/device/v1/health` reports `pending_tasks`.
- Verification passed:
  - `pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py -q --ignore=active_model`: 19 passed;
  - `py_compile` for `routes\device_gateway.py`, `device_gateway\sessions.py`,
    and `device_gateway\tasks.py`.

## 2026-05-24 Device Gateway HA Store Boundary

- User clarified the future target includes multi-process, multi-machine, and
  VPS high availability.
- Added `device_gateway/store.py` with a `DeviceTaskStore` protocol and default
  `InMemoryDeviceTaskStore`.
- Updated `device_gateway/tasks.py` so task helpers dereference the active
  store at call time, avoiding stale store references when tests or future
  Redis/Postgres adapters replace the backend.
- `/device/v1/health` now reports task store metadata:
  - `backend`;
  - `shared_across_processes`.
- Active-session send failures now unregister the broken session and best-effort
  requeue the task instead of leaving it stranded.
- Device `hello` drains all pending batches for that device, not only the first
  16 tasks.
- Sent motion tasks are tracked as per-session in-flight tasks until a
  `motion_event` acknowledges them; unacknowledged in-flight tasks are
  best-effort requeued when the WebSocket disconnects.
- Added direct store contract tests for event snapshots, FIFO requeue,
  per-device isolation, and concurrent task IDs.
- Current state:
  - one process can handle many concurrent devices and requests;
  - in-memory store is not a multi-process/multi-node HA store;
  - Redis/Postgres plus sticky WebSocket routing or a session owner/broker is
    the deployment path for VPS HA.
- Verification passed:
  - `pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py tests\test_device_gateway_store.py -q --ignore=active_model`: 28 passed.

## 2026-05-24 External Capability Radar Expansion

- User provided a second external reference batch including AnySearch Skill,
  oh-my-pi, Microsoft Agent Governance Toolkit, vibe-vibe, CloakBrowser,
  GR00T-WholeBodyControl, pocket-tts, OpenAI Symphony, Algebrica, GLM-OCR,
  nano-world-model, agent-skills, HeavySkill, Understand-Anything,
  deepclaude, and claude-context.
- Updated source-of-truth documents:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/POTPIE_COMPOSIO_BORROWING_NOTES.md`.
- Current policy:
  - treat all new projects as capability references, not runtime dependencies;
  - keep no-license, CC BY-NC, GPL/AGPL, model-weight, browser automation,
    voice/persona, OCR/document, and robotics references behind separate
    license/security/privacy/safety reviews;
  - keep writing-machine direct control as the first hardware target before
    OCR, TTS, world-model, robotics, or companion-device expansion.

## 2026-05-24 Sub-Agent Versus Agent Team Rule

- User approved adding the Sub-Agent vs Agent Team coordination principle to
  LiMa governance.
- Rule:
  - default to one owner agent plus isolated sub-agents for cleanly separable
    research, review, test, and verification work;
  - keep deeply shared implementation context inside one owner agent;
  - use Agent Teams only when real-time communication, shared task state, and
    long-lived coordination are required.
- Agent Teams now require an explicit shared-state model, ownership map, audit
  trail, conflict policy, and stop/approval gate before implementation.

## 2026-05-24 External Capability Radar Third Batch

- User provided another reference batch:
  - `mattpocock/skills`, `hfviewer.com`, `warpdotdev/warp`,
    `pascalorg/editor`, `delibae/claude-prism`, `nexu-io/open-design`,
    `walkinglabs/learn-harness-engineering`, `openai/openai-agents-python`,
    `google/adk-python`, `lsdefine/GenericAgent`, and `EvoMap/evolver`;
  - duplicate references `alash3al/stash`, `openclaw/clawsweeper`, and
    `msitarzewski/agency-agents` strengthen existing radar entries.
- Updated documents:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/LIMA_MEMORY.md`;
  - `progress.md`.
- Policy retained:
  - no runtime dependency added;
  - Warp is AGPL and Evolver is GPL, so they remain concept-only;
  - OpenAI Agents SDK, Google ADK, GenericAgent, and related frameworks are
    references for guardrails, sessions, tracing, eval/deploy separation, and
    gated self-evolution, not replacements for LiMa's control plane.

## 2026-05-24 External Capability Radar MCP Batch

- User provided TUNA mirror, TrendRadar again, OpenMontage, and a Claude MCP
  service guide with a 30-service taxonomy.
- Updated source-of-truth documents:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-23-lima-code-dev-search-tools.md`;
  - `docs/DOCUMENTATION_STATUS.md`;
  - `STATUS.md`;
  - `progress.md`.
- New durable rule:
  - Skills teach LiMa how to work; MCP connectors grant places to act.
  - MCP tools are default-off and must have task need, owner, allowlist,
    credential boundary, audit event, timeout, and failure mode before use.
  - Foundation connectors are evaluated first; business, payment, CRM,
    cloud/deploy, scraping, voice, and media connectors require separate
    privacy/security/legal/blast-radius review.
- Source interpretation:
  - TUNA is an operational mirror/reference for China/VPS dependency
    resilience, not a code dependency.
  - TrendRadar remains GPL concept-only for trend monitoring, AI brief, MCP,
    and alert routing ideas.
  - OpenMontage remains AGPL concept-only for media pipeline, artifact staging,
    provider boundaries, and skill/tool catalog ideas.
  - Official MCP reference servers are protocol/API examples, not
    production-ready services; LiMa must wrap or replace them before production
    use.

## 2026-05-24 AI Engineering Competency Map

- User provided a 2026 AI engineer interview / production AI map with 12 core
  concepts:
  prompt engineering, RAG, vector embeddings/databases, agents/tool calling,
  reasoning, memory management, streaming/async, inference optimization,
  token/cost management, fine-tuning/PEFT, LLM eval, and MLOps/deployment.
- Added `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md`.
- Updated `docs/DOCUMENTATION_STATUS.md`,
  `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`,
  `STATUS.md`, and `progress.md`.
- Durable interpretation:
  - This is a production checklist, not only an interview note.
  - Each concept maps to a concrete LiMa gate: prompt contracts, retrieval
    evidence, graph/vector index boundary, tool risk metadata, reasoning
    budgets, typed memory, async observability, route cost/latency reporting,
    budget envelopes, fine-tuning gates, eval registry, and deployment/drift
    monitoring.
  - LiMa should prefer measurable engineering controls over prompt-only claims.

## 2026-05-24 External Capability Radar Agent Voice Design Batch

- User provided:
  - `OpenBMB/VoxCPM`;
  - `firecrawl/open-lovable`;
  - `alchaincyf/hermes-agent-orange-book`;
  - `nextlevelbuilder/goclaw`;
  - `repowise-dev/claude-code-prompts`.
- Current-source checks:
  - `OpenBMB/VoxCPM` metadata reports Apache-2.0; README describes VoxCPM2 as
    tokenizer-free multilingual TTS with voice design, controllable cloning,
    streaming, and 48kHz output.
  - `firecrawl/open-lovable` metadata reports MIT; README describes a
    chat-to-React app builder using Firecrawl, model provider keys, and
    Vercel/E2B-style sandbox providers.
  - `alchaincyf/hermes-agent-orange-book` metadata has no SPDX signal, while
    README declares CC BY-NC-SA 4.0 and covers Hermes Agent learning loop,
    three-layer memory, Skills, tools, and multi-agent scenarios.
  - `nextlevelbuilder/goclaw` still has no reviewed license signal; metadata
    describes multi-tenant isolation, 5-layer security, and native concurrency.
  - `repowise-dev/claude-code-prompts` metadata reports MIT; README describes
    independently authored system/tool/agent/memory/coordinator prompts and
    prompt-engineering patterns.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no source code or prompt text copied;
  - voice cloning remains behind consent, model/weight, privacy, latency,
    serving-budget, and audio-retention gates;
  - website reconstruction remains opt-in and review/test gated;
  - non-commercial/no-license references are concept-only.

## 2026-05-24 External Capability Radar Research Subagent Batch

- User provided:
  - `mvanhorn/last30days-skill`;
  - `HKUDS/LightRAG`;
  - `https://claude.com/resources/use-cases`;
  - `VoltAgent/awesome-codex-subagents`;
  - `aiming-lab/AutoResearchClaw`;
  - `anomalyco/opencode`;
  - `2025Emma/vibe-coding-cn`.
- Current-source checks:
  - `last30days-skill`: MIT; README describes an AI agent skill for
    time-bounded research across Reddit, X, YouTube, HN, Polymarket, GitHub,
    and web sources, scored by engagement and synthesized into a grounded
    brief.
  - `LightRAG`: MIT; README describes simple/fast RAG, multimodal parsing,
    chunking strategies, role-specific LLM configuration, and OpenSearch
    storage support.
  - Claude use cases page returned 200 and is treated as product use-case
    taxonomy, not a dependency.
  - `awesome-codex-subagents`: MIT; README describes 136+ Codex-native TOML
    subagents, storage locations, sandbox defaults, and explicit delegation.
  - `AutoResearchClaw`: MIT; README describes autonomous/self-evolving
    research from idea to paper, HITL modes, anti-fabrication checks,
    benchmark manifests, budget guardrails, and OpenClaw integration.
  - `opencode`: MIT; README describes an open-source AI coding agent with
    terminal UI, package-manager installs, desktop beta, and localization.
  - `vibe-coding-cn`: MIT; README describes a Chinese planning-first Vibe
    Coding guide/workstation with prompts, skills, multilingual docs, and
    AI-pair-programming workflow.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `STATUS.md`;
  - `progress.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external source or prompt text copied;
  - social-source search requires BYO-key consent, platform-term review,
    attribution, rate limits, and privacy rules;
  - broad subagent catalogs stay reference-only unless individual subagents are
    selected with ownership, sandbox, and approval metadata;
  - autonomous paper/research output requires HITL, evidence, budget, and
    anti-fabrication gates.

## 2026-05-24 External Capability Radar Browser Search RL Batch

- User provided Hyperbrowser examples, a Feishu wiki handbook, Sirchmunk,
  MiroFish, OpenClaw-RL, gstack, Nunchi agent-cli, and the Hermes Agent site.
- Current-source checks:
  - `hyperbrowserai/hyperbrowser-app-examples`: README says MIT and describes
    browser automation, scraping/data extraction, production web apps, and API
    key requirements; GitHub API earlier returned no SPDX assertion, so keep
    license review explicit before dependency use.
  - Feishu wiki page returned HTTP 200 and exposed title
    `2026 企业级AI编程实践手册`; it is methodology background for context
    engineering, specs, rules, skills, MCP, and enterprise AI coding, with no
    observed reuse license.
  - `modelscope/sirchmunk`: Apache-2.0; README describes raw-data/indexless
    search, knowledge clustering, Monte Carlo evidence sampling,
    self-evolving knowledge clusters, real-time chat, API/SSE, and MCP.
  - `666ghj/MiroFish`: AGPL-3.0; swarm/prediction simulation concept only.
  - `Gen-Verse/OpenClaw-RL`: Apache-2.0; fully asynchronous RL loop for
    training personalized agents from natural-language feedback.
  - `garrytan/gstack`: MIT; workflow stack for planning, review, QA/browser
    testing, security, release/deploy, safety guards, cross-model review,
    gbrain setup, and multi-host skill installation.
  - `Nunchi-trade/agent-cli`: MIT; autonomous trading CLI with agent skills,
    MCP server, deterministic orchestrator, risk states, reconciliation,
    REFLECT review loop, HTTP/SSE surfaces, and testnet/mainnet split.
  - Hermes Agent site returned HTTP 200 and claims open-source/MIT status for
    a server-resident agent with persistent memory, generated skills,
    scheduled automations, isolated subagents, sandbox backends, browser/web
    control, and messaging surfaces; source license remains unverified.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency was added;
  - no external code, prompt, or Feishu document text was copied;
  - browser automation is gated by API-key custody, target-site terms,
    privacy, rate limits, and anti-abuse review;
  - AGPL/no-reuse-license sources remain concept/background only;
  - trading/finance automation is blocked;
  - live self-training from private LiMa sessions is blocked until consent,
    privacy, eval, rollback, model-storage, compute, and cost gates exist.

## 2026-05-24 External Capability Radar RAG MCP Media Batch

- User provided OpenRAG, Google Cloud generative-ai samples, RuVector,
  Agent-Reach, Qwen3-TTS, VidBee, cc-connect, bluebox, and Google MCP.
- Current-source checks:
  - `langflow-ai/openrag`: Apache-2.0; README describes intelligent
    agent-powered document search with Langflow ingestion/retrieval workflows,
    OpenSearch, Docling, reranking, multi-agent coordination, and chat UI.
  - `GoogleCloudPlatform/generative-ai`: Apache-2.0; README describes Gemini,
    Agent Platform, Agent Search, RAG/grounding, vision, audio, setup, and
    learning-resource samples.
  - `ruvnet/RuVector`: MIT; README describes self-learning vector memory,
    hybrid sparse/dense retrieval, Graph RAG, PostgreSQL/pgvector replacement
    posture, local/WASM runtime, MCP server, audit chains, and branchable data.
  - `Panniantong/Agent-Reach`: MIT; README describes internet-reach
    scaffolding for web, YouTube, RSS, GitHub, semantic web search through MCP,
    social/video/community channels, local cookie storage, `doctor`, safe mode,
    and replaceable upstream tools.
  - `QwenLM/Qwen3-TTS`: Apache-2.0 source; README describes multilingual TTS,
    custom voice, voice design, 3-second voice clone, natural-language voice
    control, streaming/non-streaming generation, DashScope API, vLLM-Omni
    examples, fine-tuning, and evaluation.
  - `nexmoe/VidBee`: MIT; README describes an Electron/yt-dlp video/audio
    downloader with RSS auto-download, queue/progress UX, Fastify API, oRPC,
    SSE events, web client, and Docker deployment.
  - `chenhg5/cc-connect`: README badge says MIT, but raw license fetch failed;
    README describes bridging local AI agents to messaging platforms, web
    admin UI, lifecycle hooks, skills, provider management, WeChat, Weibo,
    Feishu/Lark, Telegram, Slack, Discord, voice/images, cron, and 10+ agents.
  - `VectorlyApp/bluebox`: Apache-2.0; README describes indexing undocumented
    APIs, web-data extraction behind UI interactions, natural-language routine
    selection, parallel routine execution, AI-browser fallback, and context
    replay.
  - `google/mcp`: Apache-2.0; README lists Google's managed remote MCP
    servers, open-source MCP servers, Cloud Run hosting guidance, and ADK
    examples, while stating it is not an officially supported Google product.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `docs/reference/MCP_CONNECTOR_CATALOG.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency added;
  - OpenRAG, Google samples, RuVector, and Google MCP are references, not
    replacements for LiMa routing, storage, or provider custody;
  - social/cookie/proxy connectors, messaging bridges, closed-API extraction,
    cloud-control MCP, and video downloading remain default-off;
  - Qwen3-TTS voice clone/custom voice requires model/API terms, consent,
    voice safety, serving budget, latency tests, and audio retention policy.

## 2026-05-24 External Capability Radar RuView Addendum

- User provided `https://github.com/ruvnet/RuView.git`.
- Current-source check:
  - `ruvnet/RuView`: MIT; README describes beta WiFi CSI spatial sensing with
    ESP32-S3/C6-style nodes, presence, breathing/heart-rate trends,
    activity/fall signals, room mapping, Home Assistant/Matter integration,
    edge modules, witness logs, and Claude/Codex workflow plugins.
  - README limitations matter for LiMa: ESP32-C3/original ESP32 are not
    supported, single-node spatial resolution is limited, camera-free pose
    accuracy is limited, and some training/evaluation phases remain pending.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/reference/HARDWARE_COMPANION_REFERENCES.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency added;
  - RuView is a later ambient-perception and hardware-workflow reference, not
    part of the first writing-machine control loop;
  - people sensing, through-wall sensing, vital-sign trends, fall/distress
    detection, room mapping, Home Assistant/Matter automation, and
    security/medical outputs require consent, privacy/legal review, calibrated
    hardware evidence, false-positive policy, data-retention controls, and
    human review before any LiMa adapter.

## 2026-05-24 External Capability Radar Quelmap Addendum

- User provided `https://github.com/quelmap-inc/quelmap.git`.
- Current-source check:
  - `quelmap-inc/quelmap`: Apache-2.0; README describes an open-source local
    data analysis assistant with data visualization, table joins, statistical
    tests, unlimited-row/30+ table analysis posture, built-in Python sandbox,
    Ollama/local LLM defaults, OpenAI-compatible providers, Docker Compose,
    Postgres storage, and CSV/Excel/SQLite upload support.
  - README privacy warning matters for LiMa: if a provider such as OpenAI or
    Groq is configured, dataset schema is sent to that provider. External DB
    connection strings should use read-only credentials.
- Updated:
  - `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`;
  - `docs/superpowers/plans/2026-05-24-external-capability-adoption-roadmap.md`;
  - `docs/LIMACODE_MANAGEMENT.md`;
  - `docs/reference/AGENT_AUTONOMY_BORROWING_NOTES.md`;
  - `STATUS.md`;
  - `docs/LIMA_MEMORY.md`.
- Boundary retained:
  - no runtime dependency added;
  - no external code or prompt text copied;
  - Quelmap is a data-analysis workbench reference, not a default LiMa
    dependency;
  - dataset contents/schema, generated Python, external database connections,
    and cloud LLM provider calls require consent, redaction, read-only
    credentials, sandbox limits, data retention, and audit.

## 2026-05-24 External Capability Radar 10-Subsystem Addendum

- User provided a de-duplicated 10-subsystem open-source recommendation table
  for LiMa.
- Added `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md`.
- Coverage:
  - coding Worker and Agent execution;
  - backend routing and load balancing;
  - context engineering and RAG;
  - memory system;
  - evaluation and quality assurance;
  - observability and monitoring;
  - security and governance;
  - streaming and protocol enhancement;
  - infrastructure and DevOps;
  - terminal UI and developer experience.
- Current-source checks found important caveats:
  - LiteLLM and LangFuse have mixed license files or no SPDX in GitHub API;
  - Phoenix is Elastic-2.0;
  - Rebuff is archived;
  - Open Interpreter is AGPL-3.0;
  - Sourcegraph Cody and Braintrust supplied paths need current-source
    confirmation before reuse.
- Boundary retained:
  - no runtime dependency added;
  - no external code copied;
  - new projects are planning references until license, security, data-flow,
    maintenance, adapter-test, and rollback reviews pass;
  - hosted eval/observability, cloud sandbox, external DB, MCP/A2A, deployment,
    browser, messaging, and hardware permissions stay default-off.

## 2026-05-24 Implementation Review Plan

- User asked to list recent learning as a detailed implementation plan, with
  the user completing coding and Codex performing code review.
- Added:
  - `docs/superpowers/plans/2026-05-24-lima-implementation-review-plan.md`.
- Plan shape:
  - collaboration contract: user implements one slice at a time; Codex reviews
    findings first and verifies tests;
  - global rules: no dependency dump, no framework rewrite, no permission
    expansion, no private data export by default;
  - milestones: review harness, router/key-pool telemetry, async/concurrency,
    context graph/reranking, memory taxonomy, eval/quality, observability,
    worker governance/MCP/A2A, sandbox evaluation, streaming, data workbench,
    DevOps/terminal UX, and hardware companion later lane;
  - each milestone includes likely files, tests, Codex review focus, and exit
    criteria.
- Boundary retained:
  - documentation-only change;
  - no runtime dependency added;
  - no external code copied;
  - implementation remains future work to be coded by the user and reviewed by
    Codex.
