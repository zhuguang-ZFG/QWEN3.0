# LiMa Status

> Updated: 2026-05-24
> Active direction: private personal coding assistant.

## Current Summary

| Area | Status | Evidence |
|---|---|---|
| Product direction | Active | Commercial work paused; `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` is the current plan. |
| Coding backend eval | Complete for first pass | 85-candidate smoke, 16-candidate full fixture set, ranking docs and JSON results exist. |
| Coding routing | Active | `code_orchestrator.py`, `routing_engine.py`, and `router_v3.py` route coding traffic by evidence-backed tiers. |
| Cloudflare AI routing | Active | Direct `cf_*` and Worker `cfai_*` text/code models are documented and routed; Worker qwen/deepseek quick eval passed. |
| IDE context preflight | Deployed | `lima_context.py` injects request-local context into coding and Anthropic tool paths. |
| Claude Code tool path | Hardened | `/v1/messages` now guards malformed HTTP 200 tool-backend responses; real Claude Code large-file `Read` loop passed after deploy. |
| VPS safety baseline | Retained | HTTPS, headers, internal port blocking, backup practices. |
| Agent Evolution | Phase 0-5 complete | Quality gates, worker contract, roles, eval harness, evolution loop, and server APIs all implemented and tested (103 tests). |
| LiMa Code worker | Active smoke path | `/lima task <id>` now fetches a Server task, runs the guarded local runner, writes local audit evidence, and submits the result back to Server. |
| Agent control plane v0.3 | Implemented locally | Adds audit summary API, admin task audit panel, Telegram callback parsing, approved-task candidate extraction, and dry-run Server/Worker contract smoke. |
| Real-machine worker smoke v0.4 | Deployed and smoke-verified | Server worker preflight and smoke-task factory are live on VPS; LiMa Code completed public task `cfcd3f2b` and submitted `needs_review`. |
| Web-reverse model admission | Complete for first batch | 29 registered web-reverse/local-proxy backends smoked with synthetic prompts; SCNet large is `code_medium_candidate`, Kimi local is `code_floor_candidate`. |
| Memory daemon + prompt recall | Implemented locally | Server lifespan starts `session_memory.daemon`; `scripts/memory_daemon_ctl.py` can inspect status/run one cycle; `server.py` now runs prompt-time memory recall before routing. |
| Autonomous worker lifecycle | Partially implemented | LiMa Code has bounded `/lima work` loops, stop marker, failure quarantine, repo allowlist, audit, and runtime budget. Always-on daemon mode remains a later gated step. |

## 2026-05-24 Deployment And Closure Update

- VPS main router is deployed from branch `codex/free-web-ai-probe`.
- Latest pushed commit: `fdea227` (`fix: preserve local router api key`).
- VPS backups from the Server/Worker sync:
  - `/opt/lima-router/backups/agent-worker-sync-20260524_104836`
  - `/opt/lima-router/backups/runtime-deps-sync-20260524_105115`
- VPS `lima-router` restarted active; `/health` reports modules `mcp`, `agent_tasks`, and `telegram`.
- Public HTTPS smoke passed:
  - `https://chat.donglicao.com/v1/chat/completions` returned exact `lima-postdeploy-ok`.
  - `/agent/worker/preflight` returned `contract_version=agent-task-v1`.
- Real Server/Worker smoke passed:
  - Server task `cfcd3f2b` was created by `/agent/worker/smoke-task`.
  - `D:\GIT\deepcode-cli` executed `/lima task cfcd3f2b`.
  - Worker submitted `needs_review`.
  - Server events are `created,result_submitted`.
- FRP closure was rechecked after the local Windows router restart:
  - Root cause of the temporary FRP chat failure was the Windows local router process running without `LIMA_API_KEY`.
  - `D:\ollama_server\start-lima-api.ps1` now ensures the child router process receives private API key environment.
  - `local_router_start.bat` now defaults `LIMA_API_KEY`/`LIMA_API_KEYS` to `lima-local` when neither is set.
  - `http://127.0.0.1:8080/v1/chat/completions` returned exact `lima-final-local-ok`.
  - `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-final-frp-ok`.

Current known remaining planning items:

1. Continue `server.py` decomposition, with chat/completions and Anthropic handlers as the next major extraction targets.
2. Consolidate backend configuration into a single source and remove remaining capability/list duplication.
3. Wire `key_pool.py` into `http_caller.py` for multi-key providers.
4. Keep Kimi, TheOldLLM, MiMo web, and page-only web AI candidates gated until refreshed and model-level smokes pass.
5. Keep always-on worker daemon mode behind explicit repo allowlist, runtime budget, stop marker, audit, failure quarantine, and manual production gates.

## 2026-05-23 Calibrated Status

Latest local source state:

- Branch: `codex/free-web-ai-probe`.
- Latest checked commit: `8b86228` (`fix: security hardening + integrate final 4 modules`).
- LiMa target suite: `382 passed, 8 skipped`.
- This is not a plain full-repo pytest result; unrestricted collection can enter local reference repositories.

Current module reality:

| Area | Current state |
|---|---|
| Session Memory | `server.py` writes successful user/assistant turns to SQLite and now runs `session_memory.prompt_recall.apply_prompt_memory_recall()` before budget checks, identity adaptation, routing analysis, `v3_route`, OpenAI streaming, and fallback retry messages. |
| Memory daemon / compaction | `server.py` lifespan starts `session_memory.daemon`; daemon runs inbox ingestion and consolidation outside `/v1/chat/completions`. `scripts/memory_daemon_ctl.py status|run-once` provides local verification. |
| Graph Retrieval | Entity extraction, code graph retrieval, reranking, and tests exist. `routing_engine.py` currently computes `_reranked`, but formatted retrieval context is not yet injected into prompts. |
| Default context pipeline | `context_pipeline.factory.build_default_pipeline()` is implemented and tested, but `server.py` still uses explicit integration blocks rather than this factory as the single request pipeline. |
| Tool Gateway | Executor now uses `shell=False`, argument validation, copied HTTP args, and audit events. |
| Admin UI auth | API calls use `authFetch` and JS token injection is JSON-escaped. The HTML login still uses `?token=...`, so a cookie/session design remains a later hardening step. |
| Concurrency Pool | Implemented and tested as `context_pipeline.concurrency_pool.ConcurrencyPool`; it has not replaced `key_pool.py` or provider key scheduling. |

LiMa Code worker reality:

- `D:\GIT\deepcode-cli` now has a local `/lima` command runner.
- `/lima task <id>` is handled locally instead of being sent to the model as a chat prompt.
- `/lima next` claims one pending `accepted` Server task, runs it locally, and submits the result.
- `/lima work --once` and `/lima work --loop --max-tasks <n>` provide bounded worker execution; loop mode rejects unbounded runs.
- Public end-to-end smoke created Server task `4d6c02b3`, ran read-only review mode over `D:\GIT\deepcode-cli`, submitted `needs_review`, and confirmed Server events `created,result_submitted`.
- Public single-claim smoke created Server task `eb9410e1`, ran `/lima next`, submitted `needs_review`, and confirmed Server events `created,result_submitted`.
- Public bounded-loop smoke created empty-repo tasks `3428f2b5` and `ae549d08`, ran `/lima work --loop --max-tasks 2`, submitted `needs_review` for both, and confirmed `changedFileCount=0`.
- LiMa Code full verification after the bounded-loop slice: `377 passed, 7 skipped`.

Reference architecture conclusion:

- `docs/REFERENCE_PROJECT_EVALUATION.md` is the current comparison of OpenRAG and Google Cloud always-on-memory-agent.
- OpenRAG is useful for knowledge ingestion, retrieval traces, and MCP knowledge tools.
- always-on-memory-agent is more directly useful for LiMa's next memory step: background inbox ingestion, typed memory, and consolidation.

## Latest Routing Facts

- Full coding fixture passers include `github_gpt4o`, `github_gpt4o_mini`, and `or_gptoss_120b`.
- `scnet_large_ds_flash` passed local coding fixtures. Its proxy is Windows-local on `D:\ollama_server:4505`; VPS `localhost:4505` is the wrong health signal for the current FRP architecture.
- Fast coding capacity includes `cerebras_gptoss`, `groq_gptoss`, `mistral_small`, and simple-case `groq_gptoss_20b`.
- Working VPS free SCNet direct models are now active fallback capacity:
  - `scnet_ds_flash`
  - `scnet_ds_pro`
  - `scnet_qwen235b`
  - `scnet_qwen30b`
- Kimi is only partially live:
  - `cf_kimi_k26` works but is slow.
  - local `kimi`, `kimi_thinking`, and `kimi_search` run behind Windows-local port `4504`; the 2026-05-23 web-reverse admission batch passed coding/review but failed strict JSON tool output, so they are `code_floor_candidate`.
  - `stock_kimi_k2` did not return a valid smoke response.
- Web-reverse/local-proxy admission evidence:
  - `scnet_large_ds_flash` and `scnet_large_ds_pro`: 3/3, `code_medium_candidate`.
  - `kimi`, `kimi_thinking`, `kimi_search`: 2/3, `code_floor_candidate`.
  - `longcat_web`: 2/3, `code_floor_candidate`.
  - `longcat_web_research`: not a coding route candidate in current fixtures.
  - DDG: HTTP 530 during smoke.
  - OldLLM: HTTP 502 during smoke.
  - MiMo web: local cookie/auth expired; no longer a JSON adapter failure.
  - Adapter fix: `longcat_web*` and `mimo_web*` now force `stream:false` for non-stream calls.
- Cloudflare AI now has two active routes:
  - Direct account API `cf_*` models remain registered for `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN`.
  - Worker wrapper `https://ai.zhuguang.ccwu.cc/v1` exposes `cfai_llama70b`, `cfai_llama4`, `cfai_qwen_coder`, `cfai_deepseek_r1`, and `cfai_mistral`.
  - `cf_qwen_coder` and `cfai_qwen_coder` now enter the default code selection window after SCNet/GitHub winners.

## Public Endpoint State

| Endpoint | Status | Intended Use |
|---|---|---|
| `https://chat.donglicao.com/v1` | Working private HTTPS path | Real IDE/agent clients when HTTPS is preferred. |
| `http://47.112.162.80:8088/v1` | Working FRP path to Windows local router | Direct validation of local-router plus Windows proxy backends. |
| `https://api.donglicao.com/v1` | New API gateway retained | Requires a real New API token; `lima-local` is not valid there. |

Known IDE config:

```text
Base URL: https://chat.donglicao.com/v1
Alt URL:  http://47.112.162.80:8088/v1
API key:  lima-local
Model:    lima-1.3
```

See `docs/FREE_MODEL_ROUTING_STATUS.md` and `docs/LIMA_MEMORY.md`.

## Production Topology

| Component | Status |
|---|---|
| nginx HTTPS edge | Running |
| `chat.donglicao.com` | Private chat plus LiMa `/v1/*` entry |
| `api.donglicao.com` | Existing New API entry retained |
| `lima-router` | systemd service, localhost `8080` |
| New API | localhost `3003` |
| Voice gateway | localhost `8091`, not main product direction |

## Windows FRP Topology

The FRP path is closed and should be treated as production-relevant for local free web/proxy backends:

```text
IDE/client
  -> http://47.112.162.80:8088/v1
  -> VPS frps 8088
  -> Windows frpc redcode-api
  -> Windows LiMa API 127.0.0.1:8080
  -> Windows local providers on 4504/4505 when selected
```

## Active Code

| File | Role |
|---|---|
| `server.py` | OpenAI/Anthropic protocol boundary |
| `routing_engine.py` | Scenario classification and route execution |
| `router_v3.py` | Backend pools |
| `code_orchestrator.py` | Coding tier logic and quality loop |
| `lima_context.py` | Context preflight |
| `http_caller.py` | Backend HTTP transport |
| `backends.py` | Backend inventory |
| `server_lifespan.py` | FastAPI background startup/shutdown orchestration |

## Verification Record

Latest completed context-preflight verification:

```text
python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py
python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py
70 passed
```

Latest free-model VPS smoke:

- SCNet direct working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`.
- Kimi working but slow: `cf_kimi_k26`.
- Proxy-backed or invalid in smoke: `scnet_large_*`, local `kimi*`, `stock_kimi_k2`, `scnet_minimax`.

Latest free-model routing deployment:

- Backup: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Local tests: `71 passed`.
- VPS `/health`: 200.
- Public coding smoke: 200 in 4585ms.
- Public Anthropic tool smoke: 200 in 672ms with `stop_reason=tool_use`.

Latest Claude Code protocol hardening:

- Root cause class: some OpenAI-compatible free tool backends can return HTTP 200 with an empty or non-standard `choices[0].message`; older LiMa conversion could turn that into an Anthropic message with empty `content`.
- Fix: `server.py` now guarantees `_convert_response_openai_to_anthropic()` returns a valid Anthropic message with at least one content block, normalizes list-style text content, handles malformed `choices`, and emits `input: {}` in streaming `tool_use` block starts.
- Regression tests: `tests/test_anthropic_tool_protocol.py`.
- Local verification: `py_compile server.py`; focused suite returned `90 passed, 5 skipped`.
- VPS backup: `/opt/lima-router/backups/claude-tool-protocol-20260522_220037`.
- VPS deployment: remote compile passed, `lima-router` restarted active, VPS-local `/health` returned 200.
- Public verification:
  - `https://chat.donglicao.com/v1/messages` returned exact `deployed-msg-ok`.
  - Real Claude Code CLI `Read D:\GIT\server.py` returned exact `deployed-read-ok` with a two-turn tool loop and about 108k input tokens.
  - FRP health `http://47.112.162.80:8088/health` returned 200.

Latest SCNet/Kimi first-tier eval:

- Promoted to first-tier coding: `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`.
- Not promoted: `cf_kimi_k26`, `stock_kimi_k2`, local `kimi*`, `scnet_large_*`, `scnet_minimax`.
- Backup: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Public coding smoke: 200 in 3347ms.

Latest documentation/FRP verification:

- `git diff --check`: passed, with line-ending warnings only.
- `pytest --ignore=active_model`: `66 passed, 5 skipped` for the core routing/HTTP/streaming/eval/context suite.
- `http://47.112.162.80:8088/health`: 200.
- `http://47.112.162.80:8088/v1/models`: 200 with `lima-local`.
- `http://47.112.162.80:8088/v1/chat/completions`: 200, routed through LiMa.
- Caveat: `D:\GIT\active_model` is a stale junction to a deleted temp directory, so plain pytest collection fails unless ignored or the junction is cleaned.

## Paused Or Removed

- Payment and commercial platform docs.
- Billing/quota/training experiments not needed for the current personal assistant direction.
- Large reference repos and one-off debug scripts stay local unless explicitly curated.

## Latest Code Quality Review

- Review closeout doc: `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md`.
- Scope: local review only; no production deployment was performed.
- Local compile passed for the main reviewed runtime files: `server.py`, `routing_engine.py`, `router_v3.py`, `http_caller.py`, `code_orchestrator.py`, `routes/agent_tasks.py`, `routes/admin.py`, `routes/telegram.py`, and `tool_gateway/executor.py`.
- P0 implementation pass restored the route-test baseline, blocked active lease overwrite in agent task claim, and removed admin-token exposure from query-string login plus page JavaScript.
- Focused verification: `python -m pytest tests\test_agent_task_routes.py tests\test_agent_task_contract.py tests\test_access_guard.py -q --ignore=active_model` returned `40 passed`.
- Continued code review pass fixed the remaining full-suite failures and the mojibake image prompt detector.
- Current local verification: `python -m pytest -q --ignore=active_model` returned `354 passed, 8 skipped`; tracked Python `py_compile` passed for 215 files.
- Remaining warnings: FastAPI `on_event` deprecation in `routes/telegram.py` and Telegram notify coroutine warnings in tests.
- Current P1 follow-ups: decide `/v1/models` auth policy, collapse duplicated backend capability config, and keep only one retrieval injection path.

## Current Roadmap

1. Expand no-login web AI candidates conservatively: sandbox registry and reachability probe now exist; DuckAI is the first high-confidence candidate.
2. Improve backend stability: `health_tracker.py` now classifies token/session/quota/rate-limit/timeout failure states.
3. Optimize free-backend routing next: quota-aware weighted routing, latency buckets, backend quality score decay, and cheap-first/simple-task policy.

Source-of-truth docs for the next phase:

- `docs/FREE_WEB_AI_EXPANSION_PLAN.md`
- `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md`
- `docs/DOCUMENTATION_STATUS.md`
- `docs/LIMA_MEMORY.md`

Latest free web AI sandbox state:

- Registry: `data/free_web_ai_candidates.json`.
- Probe results: `data/free_web_ai_probe_results.json`.
- Reachability probe found 6/6 candidate pages return HTTP 200.
- Important boundary: this is page reachability only, not model-backend admission.
- Current branch verification: `72 passed, 5 skipped` with `pytest --ignore=active_model`; JSON registry/results validate; FRP `/health` returned 200.

Latest local reverse AI inventory:

- Added `docs/LOCAL_REVERSE_AI_STATUS.md` and `data/local_reverse_ai_inventory.json`.
- DuckAI is already reverse-engineered locally in `D:\duckai` and runs on `4500`; `/v1/models` and user-only chat pass.
- DuckAI integration blocker is LiMa request format: `http_caller.py` prepends an empty OpenAI `system` message, and DuckAI returns upstream 400 for that shape.
- DuckAI public tunnel `https://ddg.zhuguang.ccwu.cc/v1/models` currently returns Cloudflare 1033, so local `4500` is the known-good path.
- SCNet-large local proxy `4505` is working; Kimi local `4504` is running but chat returns `chat.anonymous_usage_exceeded`; TheOldLLM local `4502` exposes models but chat timed out.
- HeckAI has an existing worker draft in `D:\ollama_server\heckai-worker.js`; HIX Chat, GPT.chat, Deep-seek mirror, and PLAI.chat remain page-only candidates.
- Completed execution record: `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md`.

Latest local reverse integration increment:

- `http_caller.py` now supports OpenAI `no_system` backends and merges system/IDE text into the first user message when needed.
- DuckAI registrations now cover all six locally exposed models; DuckAI models are only late fallback in routing pools.
- DuckAI local admission: `ddg_gpt4o_mini` and `ddg_gpt5_mini` passed 3/3 coding fixtures; `ddg_claude_haiku_45` failed strict JSON; `ddg_tinfoil_gptoss_120b` returned upstream 500/cooldown.
- SCNet-large local eval now passes 3/3 for both `scnet_large_ds_flash` and `scnet_large_ds_pro`; promotion remains topology-aware because VPS `localhost:4505` is not Windows.
- Kimi `4504` still returns `chat.anonymous_usage_exceeded`, classified as `manual_refresh_required`.
- TheOldLLM `4502` still times out on chat after 30s; its current refresh/log path needs token-output redaction before more refresh work.

Latest Cloudflare Workers AI routing increment:

- New inventory doc: `docs/CLOUDFLARE_MODEL_INVENTORY.md`.
- New quick eval report: `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md`.
- Added `cfai_mistral` to `backends.py` because the Worker already exposes `mistral-small-3.1`.
- Raised `router_v3.MAX_FALLBACKS` from 5 to 8 so more strong backends can actually enter the default fallback window.
- `router_v3.select_backends("code", {})` now returns Cloudflare code capacity in the default window: `cf_qwen_coder` and `cfai_qwen_coder`.
- Worker quick eval:
  - `cfai_qwen_coder`: 1/1, 2166ms.
  - `cfai_deepseek_r1`: 1/1, 6919ms.
  - `cfai_mistral`: 0/1, Worker returned HTTP 500; keep registered but do not treat as admitted coding capacity.
- Direct account Cloudflare smoke was not run in this shell because `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_TOKEN` were not set.
- Verification: `py_compile` passed for touched Python files; `pytest test_routing_engine.py --ignore=active_model` passed `25 passed`; focused suite passed `38 passed`.

Latest Cloudflare routing VPS deployment:

- Backup: `/opt/lima-router/backups/cloudflare-routing-20260522_210441`.
- Uploaded runtime files: `backends.py`, `router_v3.py`, `code_orchestrator.py`.
- Remote compile passed for `server.py`, `routing_engine.py`, `backends.py`, `router_v3.py`, and `code_orchestrator.py`.
- `lima-router` restarted and VPS-local `/health` returned 200.
- VPS route probe: `router_v3.select_backends("code", {})` includes `cf_qwen_coder` and `cfai_qwen_coder`.
- VPS direct Cloudflare smoke: `cf_qwen_coder` returned `cf-direct-ok`.
- VPS Worker Cloudflare smoke: `cfai_qwen_coder` returned `cfai-ok`.
- Public primary smoke:
  - `https://chat.donglicao.com/v1/models`: 200.
  - `https://chat.donglicao.com/v1/chat/completions`: 200 with backend `groq_gptoss_20b` in 601ms.
- FRP health path remained healthy: `http://47.112.162.80:8088/health` returned 200.

Latest token-safe local proxy routing increment:

- New plan: `docs/superpowers/plans/2026-05-22-token-safe-local-proxy-routing.md`.
- Added `runtime_topology.py` to keep Windows-local proxy backends out of routing unless:
  - the backend is not local-only;
  - `LIMA_ENABLE_LOCAL_PROXIES` or `LIMA_RUNTIME_LOCAL_PROXIES` is set;
  - a tunnel URL override is set; or
  - the expected local port is reachable.
- `router_v3.py` now filters selected candidates through the topology guard.
- `code_orchestrator.py` now filters coding pools before trying backends.
- Local refresh scripts under `D:\ollama_server` were redacted in-place:
  - `secret_redactor.js` added.
  - Kimi/TheOldLLM refresh logs no longer print raw tokens.
  - Cloudflare API tokens are read from environment variables instead of hardcoded constants.
  - `token_refresh_server.js` no longer returns raw tokens from `/refresh`.
- Refresh scripts were not executed in this pass; only syntax/redaction behavior was verified.
- Verification:
  - `py_compile`: passed for `runtime_topology.py`, `router_v3.py`, `code_orchestrator.py`, `test_routing_engine.py`.
  - Focused suite: `70 passed`.
  - Node syntax checks: passed for edited local scripts.
  - Redactor behavior check: passed.
- VPS deployment:
  - Topology guard backup: `/opt/lima-router/backups/topology-guard-20260522_211850`.
  - Short-answer hotfix backup: `/opt/lima-router/backups/short-answer-hotfix-20260522_212816`.
  - Exact-output quality backup: `/opt/lima-router/backups/exact-output-quality-20260522_212959`.
  - Uploaded runtime files: `server.py`, `runtime_topology.py`, `router_v3.py`, and `code_orchestrator.py`.
  - Remote compile passed and `lima-router` restarted with `/health` returning 200.
- Public verification:
  - `https://chat.donglicao.com/v1/models`: 200.
  - `https://chat.donglicao.com/v1/chat/completions`: 200 with exact content `topology-ok`, backend `longcat_chat`.
  - `https://chat.donglicao.com/v1/messages`: 200 with exact content `ide-ok`.
  - `http://47.112.162.80:8088/health`: 200.
- Server quality gate now treats explicit exact-output prompts as exact-match checks, preventing short valid answers from being misclassified as `fallback_exhausted` and preventing long non-matching answers from passing.
- Final verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile server.py runtime_topology.py router_v3.py code_orchestrator.py test_routing_engine.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py tests\test_coding_eval.py tests\test_lima_context.py -q --ignore=active_model`: `73 passed`.

Latest open-phase completion:

- Completed the remaining `task_plan.md` phases:
  - Phase 5 IDE/agent verification.
  - Phase 10 free web AI expansion.
  - Phase 11 stability + free routing optimization.
- New routing module: `route_scorer.py`.
  - Scores quality, stability, latency, remaining quota, and task fit.
  - Keeps stable order as tie-breaker.
  - Excludes unproven web adapters from IDE routes.
  - Skips terminal `auth_expired`, `manual_refresh_required`, and `quota_exhausted` states.
- Free web AI admission:
  - Probe command: `D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20`.
  - Admission command: `D:\GIT\venv\Scripts\python.exe scripts\build_free_web_ai_admission.py`.
  - Evidence files: `data/free_web_ai_probe_results.json`, `data/free_web_ai_admission.json`, `docs/FREE_WEB_AI_ADMISSION.md`.
  - Result: DuckAI admitted only as late fallback; HeckAI remains adapter-draft pending; all page-only candidates remain sandbox-only with private code disabled.
- IDE/agent verification:
  - Public OpenAI-compatible smoke returned exact `phase-complete-ok`, backend `scnet_ds_flash`.
  - Public Anthropic-compatible `/v1/messages` smoke returned exact `ide-agent-complete`.
  - Real Claude Code CLI returned exact `claude-cli-ok` using `ANTHROPIC_BASE_URL=https://chat.donglicao.com`, `ANTHROPIC_API_KEY=lima-local`, and `--model lima-1.3`.
- VPS deployment:
  - Backup: `/opt/lima-router/backups/complete-open-phases-20260522_214621`.
  - Uploaded runtime files: `route_scorer.py`, `routing_engine.py`, `budget_manager.py`.
  - Remote compile passed, `lima-router` restarted, `/health` returned 200.
  - FRP `http://47.112.162.80:8088/health` returned 200.
- Final verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile route_scorer.py free_web_ai_admission.py scripts\build_free_web_ai_admission.py routing_engine.py budget_manager.py test_routing_engine.py tests\test_route_scorer.py tests\test_free_web_ai_admission.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py tests\test_coding_eval.py tests\test_lima_context.py tests\test_free_web_ai_probe.py tests\test_free_web_ai_admission.py tests\test_route_scorer.py -q --ignore=active_model`: `86 passed`.

Latest P0 router hardening:

- New plan: `docs/superpowers/plans/2026-05-22-p0-router-hardening.md`.
- Added `access_guard.py` for private API key enforcement using `LIMA_API_KEY` and/or comma-separated `LIMA_API_KEYS`.
- `/v1/chat/completions`, `/v1/messages`, `/api/live-key`, and `/v1/status` now require the private key locally.
- `/v1/images/generations` also requires the private key locally, and image dimensions are capped at 2048x2048.
- `/health` and `/v1/models` remain open for health checks and IDE model discovery.
- Admin routes now fail closed when `LIMA_ADMIN_TOKEN` is not configured.
- `_try_backend()` now accepts full fallback `messages`, so same-tier and upgrade retries do not lose multi-turn context.
- `_detect_ide()` now returns an empty string for ordinary chat instead of a truthy unknown marker, so non-IDE requests are no longer misclassified as IDE.
- Anthropic streaming responses no longer append the visible ``[LiMa -> backend]`` footer; backend selection remains internal request evidence only.
- `test_streaming.py` no longer depends on an unconfigured `pytest-asyncio` plugin; the five async streaming regression checks now execute through `asyncio.run()`.
- Local verification:
  - `D:\GIT\venv\Scripts\python.exe -m py_compile access_guard.py server.py routes\admin.py`: passed.
  - Focused P0 tests passed for access guard, fallback context, IDE detection, and image endpoint guard.
  - `tests\test_stream_footer.py`: `2 passed`.
  - `test_streaming.py`: `5 passed`.
  - Core suite with the new tests: `112 passed`.
- VPS deployment:
  - GitHub commit pushed: `c4515d3`.
  - P0 runtime backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
  - Uploaded `server.py`, `access_guard.py`, and `routes/admin.py`.
  - Added remote `LIMA_API_KEY` config because the new guard fails closed and no private key was configured.
  - Remote compile passed and `lima-router` restarted active.
  - Initial smoke immediately after restart hit a transient connection-refused window before uvicorn listened.
  - Authorized public endpoints then returned 500 because VPS `health_tracker.py` was stale and lacked `get_backend_state()`.
  - Health tracker sync backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
  - Uploaded `health_tracker.py`; remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`; `lima-router` restarted active.
  - Public `/v1/chat/completions` without auth returned 401.
  - Public `/v1/chat/completions` with auth returned exact `p0-deploy-ok`, backend `router_longcat_chat`.
  - Public `/v1/messages` with auth returned exact `p0-msg-ok`.
  - FRP `/health` returned 200.

Latest Superpowers plan closure review:

- Added `docs/superpowers/PLAN_CLOSURE_STATUS.md`.
- Reconciled historical Superpowers plan checkboxes; remaining literal `- [ ]` matches are boilerplate syntax examples, not open task items.
- Main `task_plan.md` phases remain complete.
- Current P0 hardening is classified as production closed after the explicit VPS deployment pass.

Latest code-quality hardening evidence:

- Accepted/fixed: `smart_router._has_vision_content` was disconnected, so the `cf_vision` image path is restored through the existing vision detector. `tests/test_vision_routing.py` now guards both image routing and circuit-breaker/network state.
- Accepted/fixed: Anthropic vision duration is calculated from the real request start. `tests/test_request_stats.py` covers both `_elapsed_ms()` and the `/v1/messages` image branch so duration is not written as `0` again.
- Accepted/fixed: `_record_request()` now performs IP location lookup before acquiring `_stats_lock`; statistics mutation remains inside the lock.
- Accepted/fixed: root-anchored `.gitignore` rules cover local one-off deploy/debug/run/stress probes, and tracked `scripts/` hardcoded `sk-` token literals were replaced with environment variable reads.
- Rejected/outdated: "admin routes unauthenticated" is not true for the current post-P0 API routes; the HTML admin shell is separate follow-up scope.
- Rejected/outdated: "deploy_v3.py contains plaintext password" is not true for the current file; it uses `LIMA_DEPLOY_PASS` or a key path.
- Rejected/outdated: the old `test_streaming.py` issue is stale; P0 already made the tests execute and pass.
- Deferred: `server.py` split, `BACKENDS` single source of truth, response-builder deduplication, and migration from `smart_router.cb_*` to `health_tracker`.
- Security note: previously exposed tokens should be rotated. Do not copy token values into docs, commits, or chat.
- Deployment policy: this round is local-only unless the user explicitly requests deployment later.
- Local verification: `py_compile smart_router.py server.py` passed; focused quality tests passed `5 passed`; core suite passed `117 passed`; `git grep -n "sk-" -- scripts` produced no matches.

Latest code-quality hardening security follow-up:

- Final review found that clearing only `sk-` literals was too narrow: tracked `scripts/` still had non-`sk` OneAPI/admin/provider credential literals.
- Commit `e231a5e` replaced the remaining tracked script credentials with environment-variable reads, including OneAPI admin password and provider keys.
- Sanitized tracked-script scans now report no hardcoded credential literals in `scripts/`; `compileall -q scripts` passed.
- Previously exposed credentials still need rotation outside the repository. No credential values were copied into project docs.

Latest global code-quality hardening:

- Completed `docs/superpowers/plans/2026-05-23-global-code-quality-review-plan.md` locally.
- Admin auth import-order failure is fixed and admin auth/audit code is split into focused modules.
- Runtime secret hygiene now has regression coverage for active runtime files.
- Web-reverse admission policy is explicit in backend metadata and documentation.
- Retrieval injection, server prompt-context staging, and Telegram startup/notify warning paths were simplified behind tested helpers.
- Local verification is green: compileall passed; full pytest returned `391 passed, 8 skipped`; `git diff --check` passed with CRLF warnings only.
- No VPS deployment was performed in this round.

Latest global code-quality follow-up:

- The post-hardening P1 blockers are closed locally.
- Full pytest is green again after updating prompt tests to the new LiMa联网智能助手 wording.
- `mimo_web*` are no longer in default IDE/chat pools while their admission remains `sandbox_only` and `private_code_allowed=False`.
- Core `routing_engine.route()` no longer depends on local untracked FC/tool modules for ordinary requests.
- `session_memory/prompt_recall.py` is now tracked, so prompt-time memory recall is deployable with `server_context.py`.
- Response cleaning now preserves third-party factual statements about other AI products while still cleaning first-person model identity leaks.
- Local verification: compileall passed; full pytest returned `393 passed, 8 skipped`.
- No VPS deployment was performed.

Latest LiMa Code dev-search tools:

- LiMa Code has read-only dev-search tools through MCP: `dev_search_docs`, `dev_search_error`, `dev_read_url`, `dev_fetch_github_file`, and `dev_summarize_sources`.
- The tools redact error/search input, block private URL targets, and remain outside default chat routing.
- Local verification: `compileall` passed; focused dev-search/tool/MCP suite returned `28 passed`; full pytest returned `405 passed, 8 skipped`.

Latest dev-search review follow-up:

- SSRF protection now blocks obfuscated loopback/private/link-local/metadata targets such as IPv6 loopback, decimal IPv4, hex IPv4, trailing-dot `localhost.`, and domains that resolve to non-global IPs; TinyFish fetch and dev-read share the same guard.
- Chinese dev-search triggers now include common LiMa Code phrasing for docs lookup, URL reading, and error fixing.
- MCP dev-search handlers clamp numeric arguments with stable defaults instead of returning raw `ValueError` details.
- Telegram FC/TTS helper modules are now admitted as tracked optional runtime files: `fc_caller.py`, `tool_dispatcher.py`, and `mimo_tts.py`. They remain outside ordinary routing; missing credentials degrade without network calls.
- Local verification: `compileall` passed; focused dev-search/MCP/TinyFish/Telegram suite returned `44 passed`; full pytest returned `411 passed, 8 skipped`.

Latest Telegram FC/TTS repo admission:

- Plan and evidence: `docs/superpowers/plans/2026-05-23-telegram-fc-tts-repo-admission.md`.
- `mimo_tts.py` is no longer ignored by `.gitignore`.
- `tool_dispatcher.py` is now a small compatibility facade backed by focused `lima_fc_tools` modules.
- `lima_fc_tools` modules keep the same 71 exported tool names, use ASCII schema text, and stay under 300 lines per runtime file.
- `tool_dispatcher.py` no longer exports duplicate tool names and reads `GNEWS_API_KEY` from the environment through the split information-tools module.
- `mimo_tts.py` reads `MIMO_TTS_KEY` from the environment at call time and returns `None` without opening HTTP when the key is missing.
- Clean split plan and evidence: `docs/superpowers/plans/2026-05-24-tool-dispatcher-clean-split.md`.
- Local verification: focused Telegram/local-tool/security suite returned `23 passed`; ruff passed for the split tool files; full pytest returned `418 passed, 8 skipped`.
