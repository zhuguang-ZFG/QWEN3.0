# LiMa Status

> Updated: 2026-05-31 (LiMa Code Chinese-first UX deepening closeout)
> Branch: `main`
> Tests: LiMa Code `npm.cmd run check` clean; full LiMa Code suite **495 passed, 7 skipped**; `npm.cmd run build` clean
> Current VPS: unchanged for this CLI/TUI-only slice; last server smoke health OK with `/v1/ops/summary` 200
> VPS: Memory 1454MB -> 1358MB (services restored), health check OK
> Improvement Plan: [`docs/IMPROVEMENT_PLAN_2026-05-27.md`](docs/IMPROVEMENT_PLAN_2026-05-27.md)

## 2026-05-31 LiMa Code Chinese-First UX Deepening Closeout

| Area | Status | Evidence |
|------|--------|----------|
| CLI/TUI operator language | Done | Startup banner, CLI help, slash commands, welcome workflow, model menu, status line, loading text, session list, undo panel, MCP status panel, file mention menu, AskUserQuestion prompt, and process-output controls now use Chinese-first labels |
| LiMa worker/operator text | Done | `/lima` command help, workbench/start/doctor/work-loop messages, drone probe output, worker budget stops, task runner summaries, artifact headings, Telegram event text, and empty/failure response messages were localized while preserving protocol fields |
| Cache and latency UX | Preserved | Token/cache/request meters and non-stream LiMa Router wait telemetry remain visible; internal API/JSON fields such as `status`, `tokens`, `cache`, `task_id`, and model/tool protocol values were not translated |
| Local verification | Done | Focused LiMa/UI tests `114 tests, 113 pass, 1 skipped`; `npm.cmd run check` clean; full `npm.cmd test` -> `502 tests, 495 pass, 7 skipped`; `npm.cmd run build` clean, `dist/cli.js` `621.3kb`; `git diff --check` clean |
| VPS deploy | Not needed | This slice only changes LiMa Code CLI/TUI/package source and tests; no LiMa Server route, env, deployment script, or VPS runtime changed |
| Release packaging | Pending | npm/GitHub Release asset was not rebuilt in this slice; installed Windows users need a follow-up package refresh to receive the Chinese-first UX |

## 2026-05-31 LiMa Code npm Release Refresh Closeout

| Area | Status | Evidence |
|------|--------|----------|
| npm tgz rebuilt | Done | `npm.cmd pack --json` with project-local npm cache rebuilt `lima-code-0.1.24.tgz`; package size `249519`, shasum `2d0ab22afe3f67fa64b3420c9285a6fdc4b0c7c7`, SHA256 `9d05c85101a8f0d12918305341fbae7c40f8a12d35a67f1c30ef48792f3c31a4` |
| Release asset refreshed | Done | `gh release upload lima-code-v0.1.24 lima-code-0.1.24.tgz --clobber`; GitHub Release asset digest now `sha256:9d05c85101a8f0d12918305341fbae7c40f8a12d35a67f1c30ef48792f3c31a4` |
| Install smoke | Done | Installed from `https://github.com/zhuguang-ZFG/deepcode-cli/releases/download/lima-code-v0.1.24/lima-code-0.1.24.tgz` into a local temp prefix; `lima-code --version` returned `0.1.24`; `lima-code --headless -p "/lima start" --json` returned `ok=true` with zero model calls |
| Workspace hygiene | Done | Temporary `.npm-cache` and `.pkg-smoke` directories were removed after smoke; both root and `deepcode-cli` worktrees returned clean |
| VPS deploy | Not needed | This only refreshed the npm-installable GitHub Release package; no LiMa Server code or VPS environment changed |

## 2026-05-31 LiMa Code Cache-Rate and Prompt Hygiene Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Cache hit percentage | Done | TUI status line now renders cached token count plus hit rate, e.g. `cache: 950 (73.1%)`; hit rate uses `cached/(cached+miss)` when miss telemetry exists and falls back to `cached/input` |
| Prompt readability | Done | Runtime date/model guidance now uses readable Chinese spacing instead of dense/legacy wording; tests guard against mojibake in the base LiMa Code prompt |
| Stable prompt contract | Guarded | Existing session test still proves system prompt order stays prefix-cache-friendly: tools first, default skills second, dynamic runtime context third, project instructions last |
| Local verification | Done | TDD red first: cache percentage and runtime guidance failed; focused tests `73 tests, 70 pass, 3 skipped`; `npm.cmd run check` clean; full `npm.cmd test` -> `499 tests, 492 pass, 7 skipped`; `npm.cmd run build` clean, `dist/cli.js` 612.8kb |
| VPS deploy | Not needed | No LiMa Server code, route, env, or deployment script changed in this slice |

## 2026-05-31 LiMa Code TUI Vibe Telemetry Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Reasonix-informed UX | Done | Borrowed the visible request-layer and token/cache meter idea from `esengine/DeepSeek-Reasonix`; did not copy the DeepSeek-only cache architecture |
| Router wait clarity | Done | Non-stream LiMa Router waits now render as `waiting for LiMa Router response [model]`, with retry and timeout telemetry when present |
| Status-line usage meters | Done | TUI status line now surfaces active tokens plus accumulated input/output/cache/request counts from `usagePerModel` |
| Progress model telemetry | Done | `LlmStreamProgress` carries the active request model so wait text can show which model/router request is currently blocking |
| Local verification | Done | `npm.cmd run test:single -- src/tests/loadingText.test.ts src/tests/statusLine.test.ts src/tests/session.test.ts` -> 71 tests, 68 pass, 3 skipped; `npm.cmd run check` clean; `npm.cmd test` -> 498 tests, 491 pass, 7 skipped; `npm.cmd run build` clean, `dist/cli.js` 612.3kb |
| VPS deploy | Not needed | No LiMa Server code, route, env, or deployment script changed in this slice; package/release refresh can follow if the Windows install should receive it immediately |

## 2026-05-31 VPS DNS/Proxy and Probe Timeout Closeout

| Area | Status | Evidence |
|------|--------|----------|
| VPS DNS root cause | Fixed | `/etc/resolv.conf` had been overwritten by Tailscale DNS (`100.100.100.100`) while Tailscale reported it could not reach configured DNS servers; disabled Tailscale DNS accept (`CorpDNS=false`) and restored public resolvers |
| Shell proxy hygiene | Fixed | `/etc/profile.d/proxy.sh` exported dead proxy `100.94.119.7:7890`; backed it up to `/etc/profile.d/proxy.sh.lima-disabled-20260531-1405` and disabled it; fresh SSH login has no proxy env |
| Worker provider recovery | Partially restored | After DNS/proxy repair, public probes reactivated `cfai_llama4`, `assist_brainstorm`, `cfai_qwen_coder`, `cfai_llama70b`, `scnet_ds_flash`, and `scnet_qwen30b` from fresh healthy evidence |
| Failed-provider evidence | Recorded | `StockAI` family now returns unparseable responses; `OldLLM` family returns upstream 502; `cfai_mistral` returns upstream 500; `cfai_deepseek_r1` returns empty; `google_flash_code` and `mistral_large_code` return network errors/timeouts |
| Operator probe timeout | Deployed | `POST /v1/ops/backends/probe` accepts `timeout_sec` and defaults to a bounded operator timeout; `google_flash_code` with `timeout_sec=5` returned timeout evidence in `5150ms` instead of blocking for about 130s |
| Local verification | Done | focused tests `31 passed`; full pytest `2186 passed, 10 skipped`; ruff/pyright clean |
| VPS smoke | Done | deploy uploaded 2/2 and health OK; public timeout regression returned `error_class=timeout`, `timed_out=true`, `recorded=true`; final `/v1/ops/summary` 200 shows dead backends reduced to `124` and probe candidates to `12` |

## 2026-05-31 Evidence-Based Backend Probe Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Manual backend probe | Deployed | Added private `POST /v1/ops/backends/probe`; default behavior probes and records evidence without reactivating |
| Evidence recording | Deployed | Probe results write to health tracker, backend profile, and backend telemetry with `scenario=probe` / `phase=operator_probe` |
| Cooldown bypass for operators | Deployed | Manual probe uses `ignore_cooldown=True`, so stale cooldown state does not block fresh operator evidence |
| Guarded reactivation | Deployed | `reactivate_on_success=true` only reactivates when the fresh probe returns `status=healthy`; failed probes recommend `keep_retired` |
| Local verification | Done | focused tests `33 passed`; `ruff check backend_probe_loop.py http_sync.py routes/ops_metrics.py tests/test_ops_metrics.py` clean; `pyright backend_probe_loop.py http_sync.py routes/ops_metrics.py` returned 0 errors; full pytest `2184 passed, 10 skipped` |
| VPS smoke | Done | deploy uploaded 3/3 and health OK; public `/health` 200; `groq_llama70b` probe returned healthy/recorded/reactivated=false; `cerebras_gptoss` probe returned healthy and reactivated; `assist_brainstorm` and `cfai_llama4` remained failed with DNS evidence and were not reactivated |
| Residual provider state | Visible | `/v1/ops/summary` remains `critical` with many dead/degraded/retired backends; this is now an explicit operator recovery queue rather than a silent routing failure |

## 2026-05-31 Ops/API/Tailscale Hardening Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Ops dashboard rollup | Deployed | `/v1/ops/summary` now returns status, alerts, counts, and operator action hints derived from `/v1/ops/metrics` |
| Supplier recovery UX | Deployed | Added private `POST /v1/ops/backends/retire` and `POST /v1/ops/backends/reactivate`, both requiring explicit operator evidence/reason |
| Wider API JSON contract | Deployed | Shared JSON parser now returns HTTP `400` for malformed/non-object JSON across chat, embeddings, images, public demo, outcome ingest, device gateway, Telegram webhook, and ops POST actions |
| Local verification | Done | focused ops/API route tests `69 passed`; full pytest `2181 passed, 10 skipped`; `ruff check`, `pyright`, and `git diff --check` clean |
| VPS smoke | Done | deploy uploaded 9/9 and health OK; public `/health` 200; authenticated `/v1/ops/summary` 200; malformed `/v1/ops/backends/reactivate` body returned `400 {"error":"valid JSON body required"}` |
| Git warning | Fixed | granted current Codex user read/traverse permission on `C:\Users\Administrator\.config\git\ignore` path; `git status --short` no longer emits the permission warning |
| Tailscale startup | Fixed | VPS had `tailscale` binaries but no `tailscaled.service`; added and enabled systemd unit, restored peer online; Windows status `BackendState=Running`, `HealthCount=0`, VPS online, ping `100.103.82.78` in `11ms` |

## 2026-05-31 Telegram Test-Noise Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Test placeholder token handling | Deployed | `telegram_bot.py` now logs Telegram API failures at debug level when the configured token is an obvious placeholder such as `test-token-123`; real tokens still warn |
| Local verification | Done | focused Telegram tests `30 passed`; full pytest `2171 passed, 10 skipped`; no trailing `Telegram API sendMessage failed` noise |
| VPS smoke | Done | deploy uploaded 1/1 and health OK |

## 2026-05-31 Chat JSON Guard + Tailscale Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Malformed JSON handling | Deployed | `/v1/chat/completions` and `/v1/messages` now return HTTP `400` with `invalid_request_error` instead of leaking `JSONDecodeError` as a 500 |
| Local verification | Done | chat endpoint focused tests `10 passed`; related route/body-limit tests `19 passed`; full pytest `2170 passed, 10 skipped`; `ruff check`, `pyright`, and `git diff --check` clean |
| VPS smoke | Done | deploy uploaded 1/1 and health OK; public malformed JSON smoke returned HTTP `400`; public valid chat smoke returned HTTP `200` via `groq_llama70b` |
| Tailscale install/root cause | Fixed | Windows Tailscale install failed because `iphlpsvc` was disabled; enabling IP Helper allowed Tailscale `1.98.2` to install and run |
| Tailscale connectivity | Fixed | after restarting local Tailscale service, `tailscale ping 100.103.82.78` reached `lima-server` first via DERP(sfo), then direct `47.112.162.80:53729` in `11ms`; final local status `BackendState=Running`, `Health=[]` |

## 2026-05-31 Telemetry-Driven Routing Guard Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Routing guard | Deployed | `observability/routing_guard.py` derives short-lived backend `quarantined`/`penalized` decisions from recent sanitized backend telemetry |
| Route selection | Deployed | `routing_selector.py` skips quarantined backends when alternatives exist, keeps the last available backend as a safety valve, and applies penalty multipliers to unstable candidates |
| Ops visibility | Deployed | `/v1/ops/metrics.routing_guard` exposes enabled state, time windows, hard error classes, and current backend decisions |
| Same-second ordering | Fixed | guard uses telemetry record order as well as timestamp, so a failure after a success in the same second is not accidentally cleared |
| Local verification | Done | focused routing guard/selector/ops tests `28 passed`; full pytest `2168 passed, 10 skipped`; `ruff check`, `pyright`, and `git diff --check` clean |
| VPS smoke | Done | deploy uploaded 4/4 and health OK; public `/v1/ops/metrics` returned `routing_guard.enabled=true`, `backend_telemetry.total_recent=8`, latest backend attempt success via `groq_llama70b`; public chat smoke returned HTTP `200` via `groq_llama70b` |

## 2026-05-31 Bounded Telemetry JSONL Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Runtime telemetry retention | Deployed | `observability/jsonl_store.py` appends compact JSONL and trims files above `LIMA_TELEMETRY_JSONL_MAX_BYTES` (default 1MB), preserving recent lines |
| Backend telemetry writer | Deployed | `observability/backend_telemetry.py` now uses the bounded writer with `MAX_RECENT=500` |
| CLI telemetry writer | Deployed | `observability/cli_telemetry.py` now uses the bounded writer with `MAX_RECENT=200` |
| Local verification | Done | focused telemetry tests `18 passed`; full pytest `2160 passed, 10 skipped`; `ruff check` clean; `pyright` 0 errors |
| VPS smoke | Done | deploy uploaded 3/3 and health OK; public `/v1/ops/metrics` returned `backend_telemetry.total_recent=5`, `cli_telemetry.total_recent=2` |

## 2026-05-31 Strong Tool-Backend Routing Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Large tool payload routing | Deployed | `routes/tool_forward.py` ranks large tool payloads toward strong coding/tool backends while keeping small payloads latency-first |
| Streaming tool parity | Deployed | `routes/tool_forward_stream.py` uses the same ranked tier ordering for OpenAI tool-stream forwarding |
| Normal routing support | Deployed | `routing_selector.py` boosts strong coding-tool backends when `needs_tools` and `scenario=coding` are both true |
| Local verification | Done | focused telemetry/tool/routing tests `44 passed`; `ruff check` clean; `pyright` 0 errors; full pytest `2158 passed, 10 skipped` |
| VPS smoke | Done | deploy uploaded 3/3 and health OK; public large tools payload `38176` bytes returned HTTP `200`, `finish_reason=tool_calls`, `recent_backend=mistral_large` |

## 2026-05-31 Backend Attempt Telemetry Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Backend attempt ledger | Deployed | `observability/backend_telemetry.py` records sanitized JSONL attempts with backend, scenario, request type, phase, attempt, latency, success, status, and error class; no raw prompts/errors/keys are persisted |
| Normal route coverage | Deployed | `routing_executor.execute()` records serial, skipped, serial fallback, and parallel fallback attempts with empty-response/error classification |
| Speculative fast path coverage | Deployed | `speculative_call()` records completed speculative attempts; public non-cache chat produced backend telemetry for `groq_llama70b` |
| Tool-call coverage | Deployed | OpenAI/Anthropic tool forwarding records tier1/tier2/legacy direct attempts; public tools smoke returned `finish_reason=tool_calls`, `recent_phase=tool_forward`, `recent_backend=mistral_small` |
| Ops visibility | Deployed | `/v1/ops/metrics.backend_telemetry` exposes `total_recent`, `failed_recent`, `slow_recent`, `error_classes`, `by_backend`, and sanitized recent events |
| Local verification | Done | focused tests `35 passed`; route/HTTP focused tests `34 passed`; full pytest `2155 passed, 10 skipped`; `ruff check` clean; `pyright` 0 errors; `git diff --check` clean |
| VPS smoke | Done | deploy uploaded 7/7 and health OK; public chat `200` via `groq_llama70b`; ops metrics `backend_telemetry.total_recent=3` after chat and `4` after tools smoke |

## 2026-05-31 Runtime Governance + Telemetry Aggregation Closeout

| Area | Status | Evidence |
|------|--------|----------|
| Runtime data governance | Done | `data/lima_routing_weights.json`, `data/routing_model.json`, `data/webhook_activity.json`, and `data/webhook_push_dedupe.json` removed from Git index and ignored while local runtime files remain on disk |
| Remote credential hygiene | Done | local `origin` and `gitee` remotes are plain HTTPS URLs; VPS `lima-router.service` now has `secret_environment_lines=0` and uses `/opt/lima-router/.env` only |
| Webhook retry noise | Deployed | public `POST /github/webhook` and `/gitee/webhook` return `200 {"ok":true,"ignored":true,"reason":"disabled"}` instead of 503 when disabled |
| CLI telemetry aggregation | Deployed | `/agent/learn/outcome` stores sanitized LiMa Code telemetry; `/v1/ops/metrics` exposes `cli_telemetry.total_recent=1` after public smoke |
| Supplier pool recovery visibility | Deployed | `/v1/ops/metrics.backends.recovery` exposes retired count/list, probe candidates, and manual reactivation guidance without auto-reviving failing suppliers |
| VPS environment reproducibility | Done | `scripts/check_vps_environment.py` on VPS returns `ok=true`, `missing_required=[]`; broken proxy env was bypassed for pip install with `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY` |
| VPS restart smoke | Done | after dependency install + systemd hygiene, `systemctl restart lima-router` returned 0 and public `/health` returned 200 |

## 2026-05-31 LiMa Code Model Telemetry + Tool-Call Closeout

| Area | Status | Evidence |
|------|--------|----------|
| CLI timeout/retry telemetry | Done | `runHeadless` JSON includes `timeoutMs`, `maxRetries`, `retryCount`, per-call `modelCalls[]` with latency/status/error/content/tool counts, and `outcomeReport` |
| CLI tool-call telemetry | Done | OpenAI and Anthropic tool protocols are detected; `toolCapability` reports requested/observed/protocol/toolCalls/unsupportedReason |
| Server tool history fix | Deployed | `/v1/chat/completions` routes `tools` requests before `ChatRequest` validation, so OpenAI `assistant.content:null` + `role:"tool"` history reaches the tool pipeline |
| Local LiMa Code tests | Done | `npm.cmd run test:single -- src/tests/headless.test.ts`: 4 passed; `npm.cmd run check`: clean; `npm.cmd test`: 475 pass, 7 skipped; `npm.cmd run build`: OK |
| Local LiMa Server tests | Done | focused tool/chat tests: 15 passed; `ruff check routes/chat_endpoints.py tests/test_chat_endpoints.py`: clean; full `pytest -q`: 2143 passed, 10 skipped |
| VPS deploy | Done | backup `/opt/lima-router/routes/chat_endpoints.py.bak.20260531010857`; `deploy_unified.py --files routes/chat_endpoints.py` uploaded 1/1 and health OK |
| Public smoke | Done | basic CLI smoke returned `lima_code_cli_smoke_ok`, model latency 3480ms, outcome report 398ms; tool smoke returned `lima_tool_call_ok`, observed 1 OpenAI tool call in 3267ms, then completed in 2089ms |
| Git | Done | LiMa Code submodule pushed `3cae0bc fix: expose headless model telemetry` |

## 2026-05-30 Pyright Gate Cleanup

| Area | Status | Evidence |
|------|--------|----------|
| Type gate | Local clean | full-repo `pyright` now returns `0 errors, 0 warnings, 0 informations` |
| API drift fixes | Done | memory routes, routing bridge, Telegram code tools, token sync, task service, stream forwarder, context injection, and Sentry optional imports aligned to current signatures |
| Local tests | Done | focused route/memory/tool/Telegram suite `90 passed`; full suite `2140 passed, 10 skipped in 259.33s` |
| Lint | Done | `ruff check .` passed |
| Runtime data hygiene | Done | test-written routing/webhook JSON diffs restored and left out of the commit |
| VPS deploy | Done | `deploy_unified.py --files ...` uploaded 9/9 and restarted `lima-router`; deploy health OK |
| VPS smoke | Done | public `/health` 200; authenticated public `/v1/chat/completions` 200; `/agent/memory/context?backend=groq&scenario=coding` 200 |
| VPS snapshot | Done | deployed-file snapshot saved at `/opt/lima-router/backups/pyright-clean-20260530_223900/deployed-files.tgz` |

## 2026-05-30 Public Frontend Demo Bridge

| Area | Status | Evidence |
|------|--------|----------|
| Root cause | Confirmed | `donglicao.com/api/demo` proxied directly to private `/v1/chat/completions` without `Authorization`, so backend correctly returned 401 |
| Backend fix | Deployed | added default-off `routes/public_demo.py` `/public/demo/chat` endpoint with env gate, per-IP minute cap, max token cap, message length cap, and no tools/streaming |
| Nginx fix | Deployed | `/api/demo` now proxies to `http://127.0.0.1:8080/public/demo/chat`; `nginx -t` passed and `nginx -s reload` succeeded |
| Public smoke | Done | after split deploy, `https://donglicao.com/api/demo` without token returned 200 via `groq_llama4` in 9656 ms |
| Private API guard | Done | after split deploy, unauthenticated `https://chat.donglicao.com/v1/chat/completions` returned 401; authenticated request returned 200 via `cerebras_gptoss` |
| Rollback | Ready | backup `/opt/lima-router/backups/public-demo-20260530_214412` contains backend, nginx, and `.env` pre-change copies |

## 2026-05-30 Backend Dead Alert Stabilization

| Area | Status | Evidence |
|------|--------|----------|
| Alert root cause | Confirmed | retired backend pools were retried after restart because health state was not persisted and retired state was not a routing filter |
| Upstream probes | Confirmed | stock returned unparseable responses; oldllm returned `502`; Google/Mistral direct APIs were network unreachable from VPS |
| Routing fix | Deployed | retired backends hydrate as `dead`/`retired`, are excluded from selection, and repeated retirement is idempotent |
| Test stability | Done | crash-safety Hypothesis deadline disabled; full suite `2137 passed, 10 skipped` |
| VPS smoke | Done | 4 files uploaded, `lima-router` restarted, public `/health` 200 |
| Log check | Done | no new `retirement: retired`, `dead`, or `CRITICAL` lines since new process start `2026-05-30 21:08:34 CST` |

## 2026-05-30 Whole-Project Code Quality Audit

| Area | Status | Evidence |
|------|--------|----------|
| Ruff cleanup | Done | `ruff check --select F401,F841,F811,F821` and full `ruff check .` passed |
| Dead/duplicate code | Done | unused imports/vars cleaned; Telegram dev-skill duplicate command flow centralized |
| Compatibility | Done | public re-exports restored where tests/importers depend on them |
| Test stability | Done | full suite `2130 passed, 10 skipped in 211.72s` |
| VPS deploy | Done | backup `/opt/lima-router/backups/quality-audit-20260530_201229/runtime-before.tgz`; 126/126 uploaded |
| VPS/public smoke | Done | VPS-local `/health` 200; public `/health` 200; authenticated public chat 200 via `cerebras_gptoss` |
| Deploy tooling | Done | `deploy_unified.py` no longer leaks SSH exec channels and now restarts through systemd with health polling |

## 2026-05-28 Phase A+B+C Improvement Plan

### Phase A: 路由核心路径 (previously complete, verified)

| Item | Status | Key Module |
|------|--------|------------|
| A1: 路由+代码上下文 | ✅ | `routing_engine.py:121-133` → `code_context_injection.scan_and_build_context` |
| A2: 路由+学习闭环 | ✅ | `routing_weights` + `health_tracker` + `sticky_session` + `routing_selector` |
| A3: Telegram开发者技能 | ✅ | `/investigate` `/review` `/ship` `/learn` all registered |

### Phase B: 厚化编码能力 (patches applied 2026-05-28)

| Item | Status | Change |
|------|--------|--------|
| B1: 代码变更感知 | ✅ | `auto_indexer` + `file_watcher` + tree-sitter (previously complete) |
| B2: 响应后处理 | ✅ +patch | Added `os.system`/`os.popen` security patterns to `response_validator.py` |
| B3: 会话记忆增强 | ✅ +patch | Wired `skill_store.recall()` → backend priority boost; inject `code_fact`/`routing_lesson` into coding context |

### Phase C: 精简整合 (deployed 2026-05-28)

| Action | Result |
|--------|--------|
| Services audit | 5 services evaluated, all restored (user request) |
| VPS deploy | 3 files uploaded, lima-router restarted, health OK |
| Smoke test | `backend=longcat_thinking` — routing functional |
| Memory | 1358MB used (down from 1454MB pre-restart) |

## 2026-05-27 M1-M5 Capability Thickening

| Milestone | What | Files | Tests |
|-----------|------|-------|-------|
| M1: Real Execution | shell/git/network executor with preflight gates | 3 new, 1 modified | 32 |
| M2: Code Context | tree-sitter multi-language + SQLite graph + ChromaDB vector | 4 new, 4 modified | 31 |
| M3: Pipeline Integration | memory persistence + routing bridge | 2 new, 2 modified | 14 |
| M4: Developer Skills | /investigate /review /ship /learn | 5 new | 13 |
| M5: Research Orchestration | multi-source parallel search + synthesis | 4 new | 11 |

## 2026-05-27 VPS Cleanup

| Action | Result |
|--------|--------|
| Python 3.6 removed | 54MB freed, python3 → 3.11 |
| Conda package cache | 985MB freed |
| Python build artifacts | 171MB freed |
| Journal logs vacuumed | 257MB freed |
| Unused podman images | ~80MB freed |
| Total disk | 22G → 21G (55% used) |

## 2026-05-26 P2-26…32 Enhancement Blitz

| Slice | Area | Status |
|-------|------|--------|
| P2-26 | Pyright enforce (37→0) + Litestream config + Filesystem MCP (3 tools) | **Done** VPS verified |
| P2-27 | GitHub MCP native tools (5 issue/PR tools) | **Done** VPS verified |
| P2-28 | Renovate auto-deps + Hypothesis property tests (21 routing+fs) | **Done** |
| P2-29 | public_apis split (318+128) + deptry CI enforce + requirements sync | **Done** VPS verified |
| P2-30 | Hypothesis security tests (AST calc sandbox, 9 tests) | **Done** |
| P2-31 | Thread safety fix (code_orchestrator_context defaultdict lock) | **Done** VPS verified |
| P2-32 | Memory embedding bridge (Jina AI) + 4-tier semantic search fallback | **Done** VPS verified |
| P2-33 | GitHub code search + PR + branch + file contents (9 tools total) | **Done** VPS verified |
| P2-34 | memory_stats MCP tool (24 tools total) | **Done** VPS verified |
| P2-35 | ESP32 Wokwi sim + MQTT device bus + structured logging/Prometheus | **Done** VPS verified |

### New Infrastructure (P2-35)

| Capability | Module | Status |
|------------|--------|--------|
| ESP32 Wokwi sim | `esp32S_XYZ/firmware/u1-grbl/wokwi.toml` | Config ready; stepper/limit/UART/OLED virtualized |
| MQTT device bus | `device_gateway/mqtt_topics.py` + `mqtt_client.py` | Topic contract + stub daemon; paho-mqtt ready |
| Structured JSON logging | `observability/structured_logging.py` | OTEL-compatible format; `LIMA_STRUCTURED_LOGGING=1` |
| Prometheus metrics | `observability/prometheus_metrics.py` + `/v1/ops/metrics/prometheus` | Counters/histograms; `LIMA_PROMETHEUS_METRICS=1` |

### MCP Tool Inventory (24 total)

| Category | Count | Tools |
|----------|-------|-------|
| Code Search | 5 | search_repo, dev_search_docs, dev_search_error, dev_search_codesearch, dev_search_gitee |
| Filesystem | 3 | read_file, list_directory, glob_search |
| Knowledge | 6 | search_memory, get_retrieval_trace, dev_read_url, dev_fetch_github_file, dev_fetch_gitee_file, dev_summarize_sources |
| GitHub | 9 | create_issue, list_issues, get_issue, add_issue_comment, search_issues, search_code, get_file_contents, create_pull_request, create_branch |
| Ops | 1 | memory_stats |

### CI Gates

| Gate | Before | After |
|------|--------|-------|
| Pyright | report-only (37 errors) | **enforce (0 errors)** |
| deptry | report-only | **enforce (clean)** |
| pip-audit | enforce | enforce |
| gitleaks | enforce | enforce |

### Bug Fixes This Session

| Bug | File | Impact |
|-----|------|--------|
| `decide_topology()` import broke `assess_complexity()` | routing_engine.py:115 | Complexity assessment never ran |
| `ide_source=` kwarg mismatch | routing_engine.py:117 | TypeError in complexity path |
| `quality_gate_direct/tiers.py` missing on VPS | deploy script | 5 restart failures until sync |

## Current Summary

| Area | Status | Evidence |
|---|---|---|
| Product direction | Active | Commercial work paused; `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` is the current plan. |
| Project operating constraint | Active | `AGENTS.md` records that the agent may proactively deploy to the LiMa VPS for validation and multi-end joint debugging when it accelerates real production usefulness, with backups, scoped diffs, smoke checks, and rollback evidence. |
| Productivity/productization constraint | Active | `AGENTS.md` and `docs/superpowers/plans/2026-05-25-productivity-infrastructure-review.md` require all LiMa work to serve real productivity, productization, and LiMa's own distinctive character; execution closure beats decorative features. |
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
| Mastery loop | Implemented locally | `mastery_loop/` stores evidence-backed module mastery, weak points, schedules, and recommendations; agent skill promotion now requires mastery evidence refs. |
| Online distributions | Tracked | Official website, open platform, chat interface, FRP path, nginx snapshots, systemd snapshots, and smoke script are recorded in `docs/ONLINE_DISTRIBUTIONS.md`, `infra/vps/`, and `scripts/smoke_online_distributions.py`. |
| Reference migration compatibility | Closed | Original planned import/doc paths `code_context.retriever` and `docs/OPS_ENTRYPOINTS.md` are present as compatibility facades. |
| External capability radar | Ledger active | `docs/REFERENCE_IMPLEMENTATION_LEDGER.md` records 64 reference mappings plus 9 blocked gates with implemented/gated/concept/implementing/rejected status; unimplemented capabilities remain behind license, security, privacy, and safety gates. |
| Reference capability Phase 2-8 | Active with Phase 7 artifact bundle | Code intelligence, memory/mastery, agent/tool governance, MCP access plane, eval registry, LiMa Code artifact bundles, and hardware protocol-family slices have LiMa-owned interfaces, tests, and ledger evidence; latest Server suite passed `1240 passed, 8 skipped`; latest LiMa Code verification reported `0 fail, 6 skipped`; VPS baseline deployed at `ad7cab5` with public smoke `12/12`, worker preflight ready, and fake U8 WSS loop passed. |
| LiMa Code repository management | Tracked | `deepcode-cli` is pinned as a Git submodule at `8e680ea` and governed by `docs/LIMACODE_MANAGEMENT.md`. |
| esp32S_XYZ product backend | Tracked and fake-U8 integrated | `esp32S_XYZ` is pinned as a Git submodule at `160e526`; LiMa is the planned AI/backend control plane, and the product repo now includes `tools/fake_lima_u8` for the LiMa `/device/v1/ws` fake-device loop. |
| LiMa Device Gateway | Public Redis HA smoke path deployed | `/device/v1/*` supports multi-device concurrency, Redis pending-to-processing task delivery with motion-event ack cleanup, stale processing recovery hooks, publish-failure degradation, and Redis pub/sub session-owner notification for multi-process delivery; `chat.donglicao.com/device/v1/*` is exposed behind per-device token auth. Postgres remains deferred for audit/history, not realtime WebSocket delivery. |
| P0.1 ESP32 Motion Executor Contract | Deployed and smoke-verified | `MotionErrorCode` enum (8 codes), normalized motion failure errors, no-queue invalid task handling, `path_validator.py`, fake-U8 `--test failure`, default board `E_UNSUPPORTED_BOARD`, and zhuguang failure events are implemented; review fixes passed `1218 passed, 8 skipped`; VPS backup `/opt/lima-router/backups/p01-motion-contract-20260525_072701/runtime-before.tgz`; public smoke `12/12`; fake-U8 WSS success and failure loops passed. |
| P0.4/P0.5/P0.7 Device productivity slice | Deployed and smoke-verified | Real text/SVG/path pipeline, intent parser, and `/v1/ops/metrics` landed in `e3dbb9b`; review fixed preview SVG truncation, control command projection, ops metrics state access, and production-shaped backend call stats. Verification: focused `31 passed`; previous full suite `1239 passed, 8 skipped`; VPS/public smoke `12/12`; public ops metrics HTTP 200; `write LiMa` keeps a complete preview SVG; `home` queues a control task without error. |
| PROD-008 learning loop | Complete locally | `session_memory/learning_loop.py` ingests LiMa Code task results into memory, prompt profiles, routing feedback, and eval candidates; route/prompt behavior remains evidence-only until an explicit eval gate promotes it. Review verification: focused Channel Gateway + learning loop tests `106 passed`; full suite **1530 passed, 10 skipped** (2026-05-26). |
| Channel Gateway (`/channel`) | Implemented; WeChat product retired | HTTP 契约与 `channel_gateway/` 保留；`WECHAT_BRIDGE_ENABLED=0`。访客入口 **https://chat.donglicao.com**。见 `docs/WECHAT_RETIRED.md`、`docs/NEXT_MILESTONES.md`。 |
| Code quality (P0/P1/P2) | P0/P1.3 done; P2 started | `code_orchestrator` + `agent_task_evolution` split; pipeline authority tests — `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`. |
| Next milestones (four tracks) | Active doc | Coding backends, LiMa Code Worker, ESP32/Device Gateway, code quality: `docs/NEXT_MILESTONES.md`. |

## 2026-05-25 Current P0 Panorama

| ID | Status | Next Gate |
|---|---|---|
| PROD-003 | ESP32 firmware compile passed. | Hardware flash and real-device motion smoke. |
| PROD-004 | Path pipeline complete: stroke font, SVG path parser, path preview, safety bounds. | Keep fake-U8/VPS smoke in the release gate. |
| PROD-005 | Intent parser upgraded with deterministic patterns, confidence, rejection reasons, and gated LLM replanning. | Feed outcomes into P0.8 learning loop later. |
| PROD-006 | LiMa Code artifact bundle complete: `/lima plan`, `/lima test`, `/lima review`, and `/lima ship` write reviewable files under `.lima/artifacts/<task_id>/`. | Use artifact bundles as the evidence source for the learning loop and Server review. |
| PROD-007 | Ops metrics endpoint deployed and smoke-verified. | Add deeper correlation as incidents expose gaps. |
| PROD-008 | Learning loop complete locally: task outcomes feed memory, prompt, routing evidence, and eval candidates. | Keep behavior changes behind explicit eval/release gates. |

## 2026-05-25 Channel Gateway V1 Guest Safety（微信产品通道已退役 2026-05-25）

> **2026-05-26:** 真机微信/iLink/WCF 已放弃。下列为 `/channel` HTTP 契约实现记录；smoke 脚本已归档至 `scripts/archive/wechat_retired/`。

- Added `/channel/v1/bind/start`, `/channel/v1/wechat/message`, and
  `/channel/v1/wechat/health` behind sidecar bearer-token auth.
- New bindings default to `guest`; `owner` requires precomputed
  `LIMA_CHANNEL_OWNER_HASHES`.
- Guest commands:
  `/chat`, `/code`, `/draw`, `/demo`, `/about`, `/reset`, `/pause`, `/resume`,
  `/unbind`, `/help`, and `/bind`.
- Owner-only commands:
  `/code-task`, `/device`, `/status`, `/artifact`, and `/memory`.
- Review fixes:
  - owner-only commands now dispatch to explicit owner stubs for owner bindings;
  - sidecar authorization now requires `Bearer <token>` and uses constant-time
    comparison.
- Verification:
  - focused Channel Gateway + learning loop tests: `106 passed`;
  - archived smoke `scripts/archive/wechat_retired/scripts/smoke_wechat_channel_gateway.py`: 14/14 guest steps passed (historical);
  - full suite: `1346 passed, 8 skipped`.

## 2026-05-25 LiMa Server, LiMa Code, And ESP32 Joint Debug

- Server to LiMa Code public worker path was verified through `chat.donglicao.com`: smoke task `92820005` was fetched by `D:\GIT\deepcode-cli`, completed as `needs_review`, and submitted back to Server.
- Local Windows LiMa router was restarted from current `D:\GIT\server.py`; `/health` now reports `device_gateway=true` and `/device/v1/health` returns `status=ok`.
- Local esp32 fake U8 WebSocket loop passed against `ws://127.0.0.1:8080/device/v1/ws`: hello, heartbeat, transcript-to-motion-task, progress, and done acknowledgements all completed.
- Public device gateway nginx route is deployed through `https://chat.donglicao.com/device/v1/*` with per-device token auth. This was first verified in memory-only mode and superseded by the Redis HA deployment below.
- VPS nginx config backup: `/root/secure-service-backups/chat.donglicao.com.conf.codex-device-20260525_013718`.
- Public verification passed: initial `device_gateway_https_ok` returned `11/11`, and `tools/fake_lima_u8/app.py` completed the full `wss://chat.donglicao.com/device/v1/ws` loop for `dev-joint-1`. Latest Redis HA public verification is recorded below.

## 2026-05-25 Productivity Infrastructure Review

- Added the global rule that all LiMa work must serve real productivity,
  productization, and LiMa's own distinctive character.
- Reviewed LiMa Server, LiMa Code, and ESP32 across the production path rather
  than feature count. Highest-value weak spots are:
  - ESP32 motion tasks need universal structured failure events and no silent
    no-op default behavior;
  - Device Gateway `write_text`/`draw_generated` still need a real
    text/vector/path pipeline instead of placeholder geometry;
  - LiMa Code stage commands need artifact bundles and model-backed planning to
    become a true plan/patch/test/ship workflow;
  - observability, memory, prompts, and routing need a single outcome feedback
    loop tied to request/task/device ids.
- New active plan:
  `docs/superpowers/plans/2026-05-25-productivity-infrastructure-review.md`.

## 2026-05-25 P0.1 Motion Contract Deployment

- Review fixed two production gaps before deploy:
  - firmware-style `error_code`/`error_message` motion events and fake-U8
    nested `error` events are normalized into one stored `error` object;
  - tasks that fail Server-side validation are returned as `status=failed` and
    are not queued or dispatched to devices.
- Local verification after review fixes:
  - focused Device Gateway suite: `49 passed`;
  - full LiMa suite: `1218 passed, 8 skipped`;
  - touched Python compile passed.
- VPS deployment:
  - deployed commit `4a7faed` to `/opt/lima-router`;
  - runtime backup:
    `/opt/lima-router/backups/p01-motion-contract-20260525_072701/runtime-before.tgz`;
  - remote compile used `/usr/local/bin/python3.10` because system `python3`
    is `3.6.8` while `lima-router.service` runs Python 3.10;
  - `lima-router` restarted active and `/health` returned `status=ok`.

## 2026-05-25 P0.4/P0.5/P0.7 VPS Deployment

- Deployed local commit `b22b3bd` to `/opt/lima-router` for the Device
  Gateway productivity slice.
- Backup evidence:
  - full slice overlay backup:
    `/opt/lima-router/backups/p04-review-20260525_080630/runtime-before.tar`;
  - ops metrics hotfix backup:
    `/opt/lima-router/backups/ops-metrics-fix-20260525_081216/runtime-before.tar`.
- Production-only issue found and fixed during smoke:
  - `/v1/ops/metrics` initially returned HTTP 500 because production
    `backend_calls` values are dictionaries, not numeric counters;
  - the endpoint now normalizes counts and exposes `backend_call_details`.
- Verification:
  - focused local tests: `31 passed`;
  - remote compile with `/usr/local/bin/python3.10`: passed;
  - `lima-router` restarted active;
  - VPS-local `/health` and `/device/v1/health`: HTTP 200;
  - VPS-local and public `/v1/ops/metrics`: HTTP 200;
  - public online distribution smoke with exact `p04_review_ok`: `12/12`;
  - Device Gateway HTTP task smoke: `write LiMa` preserved complete
    `preview_svg`; `home` returned `capability=home` with no task error.
- Smoke cleanup:
  - temporary `codex-smoke-p04` Redis pending/processing queues were deleted.
- Residual risk:
  - PROD-003 ESP32 firmware compile has passed; hardware flashing and
    real-device smoke remain pending;
  - Postgres remains deferred for audit/history, not realtime WebSocket
    delivery.
- Public verification:
  - `scripts/smoke_online_distributions.py --api-key lima-local --chat-exact p01_motion_contract_ok` passed `12/12`;
  - Device Gateway health reported Redis task store/session bus and listener alive;
  - HTTP firmware-style failure event returned `motion_event_ack` with phase `failed`;
  - fake-U8 WSS success loop for `dev-joint-1` produced `progress` then `done`;
  - fake-U8 WSS failure loop for `dev-ha-cross` produced `accepted` then `failed`
    with `E_MISSING_PATH`.
- ESP32 submodule advanced to `160e526` to fix fake-U8 compatibility with both
  `websockets` `extra_headers` and `additional_headers` APIs.

## 2026-05-25 Device Gateway Redis HA Slice

- Added a Redis-backed Device Gateway task store for shared task ids, task snapshots, motion events, and per-device pending queues.
- Added a Redis-capable task notifier so tasks created in one router process can wake the process that owns the device WebSocket.
- Hardened the Redis queue semantics after review: pending tasks are atomically moved to per-device processing queues, motion events ack processing entries, stale processing tasks can be recovered by processing age, notifier callback failures no longer kill the listener, and publish failures degrade to queued responses instead of HTTP 500.
- `requirements_server.txt` now includes the Python `redis` package for reproducible HA deployments.
- HA mode is default-off and enabled with `LIMA_DEVICE_TASK_STORE=redis`, `LIMA_DEVICE_SESSION_BUS=redis`, and `LIMA_DEVICE_REDIS_URL`.
- Postgres remains a later audit/history store, not part of the realtime WebSocket delivery path.
- VPS Redis HA deployment is active:
  - code backup: `/opt/lima-router/backups/codex-device-ha-20260525_015208`;
  - env backup: `/root/secure-service-backups/lima-router.env.codex-device-ha-20260525_015208`;
  - Redis config backup: `/root/secure-service-backups/redis.conf.codex-device-ha-20260525_015305`.
- Verification passed: focused Device Gateway suite initially `31 passed`, then `35 passed` after reliable-queue review fixes; agent/device subset `49 passed`; public fake U8 loop completed over `wss://chat.donglicao.com/device/v1/ws`; temporary two-process test delivered a task created on `127.0.0.1:18080` to the main public WebSocket session via Redis pub/sub; online distribution smoke passed `12/12` with device backend `redis` and public `6379` guard.
- Redis is bound to loopback and VPS self-check reports public `47.112.162.80:6379` blocked while `127.0.0.1:6379` remains reachable.

## 2026-05-25 Reference Capability VPS Baseline

- VPS `/opt/lima-router` was updated from local `git archive HEAD` at commit `ad7cab5`.
- Runtime backup: `/opt/lima-router/backups/codex-baseline-20260525_031146/runtime-before.tgz`.
- Remote compile passed for core router, agent, MCP, memory, eval, tool gateway, Device Gateway, and context pipeline modules.
- `lima-router` restarted active; VPS-local `/health` returned `status=ok` with `device_gateway`, `mcp`, `agent_tasks`, and `telegram` modules true.
- Public online distribution smoke passed `12/12` with exact chat token `baseline_ad7cab5_ok`, Redis Device Gateway health, FRP health, models, and public internal-port guards including `6379`.
- Authenticated `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`, latest task `92820005`.
- Public fake U8 loop over `wss://chat.donglicao.com/device/v1/ws` completed: `hello_ack`, `heartbeat_ack`, `motion_task`, and two `motion_event_ack` frames.

## 2026-05-25 LiMa Code Phase 7 Workflow Slice

- LiMa Code submodule advanced to `8e680ea` (`feat(lima): add artifact bundle for plan/test/ship/review commands`).
- `/lima plan` writes `plan.md`, `context.json`, and `risks.md`.
- `/lima test` writes `tests.json` with command, exit code, duration, stdout, and stderr.
- `/lima review` writes `review.md` and `diff.patch`.
- `/lima ship` writes `ship.md` and `diff.patch` with changed files, test evidence, residual risks, rollback notes, commit summary, and review checklist.
- Artifact bundles are stored under `.lima/artifacts/<task_id>/` so people and Server can review structured evidence without reading terminal scrollback.
- Verification in `D:\GIT\deepcode-cli` passed:
  - `npm.cmd run check`
  - LiMa Code suite -> `0 fail, 6 skipped`
  - `git diff --check`
- LiMa Server verification passed `1240 passed, 8 skipped`.

## 2026-05-24 Deployment And Closure Update

- VPS main router is deployed from branch `codex/free-web-ai-probe`.
- Latest deployed runtime commit: `ad7cab5` (`docs: add vps verification operating constraint`).
- VPS backups from the Server/Worker sync:
  - `/opt/lima-router/backups/agent-worker-sync-20260524_104836`
  - `/opt/lima-router/backups/runtime-deps-sync-20260524_105115`
  - `/opt/lima-router/backups/lifespan-extract-20260524_111647`
  - `/opt/lima-router/backups/chat-models-extract-20260524_113220`
  - `/opt/lima-router/backups/chat-request-utils-20260524_114403`
  - `/opt/lima-router/backups/backend-registry-keypool-20260524-120642`
  - `/opt/lima-router/backups/endpoints-keypool-closed-20260524-123145`
  - `/opt/lima-router/backups/mastery-loop-20260524-125511`
- VPS `lima-router` restarted active; `/health` reports modules `mcp`, `agent_tasks`, and `telegram`.
- VPS online distribution governance:
  - `docs/ONLINE_DISTRIBUTIONS.md` now treats the official website, open platform, chat interface, FRP path, nginx edge, and supporting public services as LiMa distributions.
  - `infra/vps/nginx/` stores sanitized nginx snapshots for `www.donglicao.com`, `api.donglicao.com`, and `chat.donglicao.com`.
  - `infra/vps/systemd/` stores sanitized `lima-router.service` and `lima-voice.service` snapshots.
  - `scripts/smoke_online_distributions.py` provides repeatable public smoke checks.
  - Provider-key-like environment lines were removed from VPS systemd unit files and moved to root-readable env files; root-only backups live under `/root/secure-service-backups`.
  - Historical online distribution smoke passed: official website, open platform, chat UI, chat health, FRP health, chat models, exact chat, and internal-port guard checks returned `10/10`. Latest smoke is `12/12` after Device Gateway Redis HA and public `6379` guard.
- Public HTTPS smoke passed:
  - `https://chat.donglicao.com/v1/chat/completions` returned exact `lima-postdeploy-ok`.
  - after the lifespan extraction deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `lima-lifespan-deploy-ok`.
  - after the chat model extraction deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `deploy_https_ok_1134`.
  - after the chat request helper extraction deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `request_utils_https_ok`.
  - after the backend registry/key-pool deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `backend_registry_https_ok`.
  - after the endpoint/key-pool closure deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `endpoints_closed_https_ok`.
  - after the mastery-loop closure deploy, `https://chat.donglicao.com/v1/chat/completions` returned exact `mastery_loop_https_ok`.
  - `/agent/worker/preflight` returned `contract_version=agent-task-v1`.
  - after the chat model extraction deploy, `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`, latest task `cfcd3f2b`.
  - after the backend registry/key-pool deploy, `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.
  - after the mastery-loop closure deploy, `/agent/worker/preflight` returned `ready=true`, `contract_version=agent-task-v1`.
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
  - after the lifespan extraction deploy, `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-lifespan-frp-ok`.
  - after the chat model extraction deploy, `http://47.112.162.80:8088/v1/chat/completions` returned exact `lima-chat-models-frp-ok`.
  - after the chat request helper extraction deploy, `http://47.112.162.80:8088/v1/chat/completions` returned exact `request_utils_frp_ok`.
  - after the endpoint/key-pool closure deploy, `http://47.112.162.80:8088/v1/chat/completions` returned exact `endpoints_closed_frp_ok`.
  - after the mastery-loop closure deploy, `http://47.112.162.80:8088/v1/chat/completions` returned exact `mastery_loop_frp_ok`.
- Backend registry/key-pool closure:
  - `backends.py` now owns shared proxy/capability sets and helper predicates used by `smart_router.py` and `context_pipeline/reflection.py`.
  - `http_caller.py` now selects provider keys through `key_pool.py`, bootstraps pools from `LIMA_KEY_POOL_<PROVIDER>`, and reports success/failure back to the pool.
  - Local verification passed: focused registry/key-pool suite `58 passed`; expanded runtime regression `110 passed`; secret/request/vision/free-web admission suite `10 passed`; local and remote `py_compile` passed.
  - Public FRP chat after deploy returned exact `backend_registry_frp_ok`.
- Endpoint/key-pool closure:
  - `routes/chat_endpoints.py` owns `/v1/chat/completions` and `/v1/messages` HTTP parsing, rate limiting, vision short-circuiting, and protocol wrapping.
  - `routes/system_endpoints.py` owns `/v1/models`, `/health`, `/api/live-key`, and `/v1/status`.
  - `server.py` is reduced to app setup plus core runtime helpers; it no longer declares direct business endpoint decorators.
  - `key_pool.pool_snapshot()` now gives redacted active/cooled/blocked provider telemetry without exposing raw keys.
  - Local verification passed: endpoint/key-pool focused suite `62 passed`; expanded runtime regression `128 passed`; remote `py_compile` and import smoke passed.
- Mastery-loop closure:
  - `mastery_loop/` is deployed on VPS with typed records, SQLite store, event adapters, scoring, weak-point extraction, scheduling, recommendations, and traces.
  - `agent_evolution` and `/agent/skills/{skill_id}/promote` require eval pass, manual approval, and mastery evidence refs before activation.
  - Local verification passed: focused mastery/evolution/route suite `40 passed`; expanded runtime regression `144 passed`; remote `py_compile` and import smoke passed.

Current known remaining planning items:

1. No active architecture backlog remains from the requested backend config, key-pool, endpoint, or `server.py` route-decomposition items.
2. TechSpar-inspired mastery loop Phase 0-5 and the agent-evolution promotion gate are implemented locally; admin UI exposure and hot-path behavior changes remain intentionally gated.
3. Kimi, TheOldLLM, MiMo web, and page-only web AI candidates remain intentionally gated until refreshed and model-level smokes pass.
4. Always-on worker daemon mode remains intentionally gated behind explicit repo allowlist, runtime budget, stop marker, audit, failure quarantine, and manual production approval.

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
| Graph Retrieval | Entity extraction, code graph retrieval, reranking, prompt injection, retrieval trace, and MCP/admin trace access are implemented and tested through the shared `inject_retrieval_context()` path. |
| Default context pipeline | `context_pipeline.factory.build_default_pipeline()` is implemented and tested, but `server.py` still uses explicit integration blocks rather than this factory as the single request pipeline. |
| Tool Gateway | Executor now uses `shell=False`, argument validation, copied HTTP args, and audit events. |
| Admin UI auth | API calls use `authFetch` and JS token injection is JSON-escaped. The HTML login still uses a query-token parameter, so a cookie/session design remains a later hardening step. |
| Concurrency Pool / Key Pool | `context_pipeline.concurrency_pool.ConcurrencyPool` remains a separate tested primitive; active provider key scheduling is handled by `key_pool.py` with HTTP caller integration and redacted telemetry. |

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
- TechSpar is implemented as the local `mastery_loop/` evidence layer: module mastery, weak points, review scheduling, recommendations, and promotion evidence gates.

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

Latest external capability radar MCP batch:

- Added TUNA mirror, OpenMontage, repeated TrendRadar details, and the
  user-provided MCP guide to the external capability radar and adoption
  roadmap.
- Added `docs/reference/MCP_CONNECTOR_CATALOG.md` as the source of truth for
  candidate MCP connectors and least-privilege enablement.
- Policy retained: Skills teach workflow; MCP connectors grant authority. MCP
  tools are default-off unless a task has need, owner, allowlist, credential
  boundary, audit event, timeout, and failure mode.
- OpenMontage remains AGPL concept-only; TrendRadar remains GPL concept-only;
  TUNA is an operational mirror reference, not a code dependency.

Latest AI engineering competency map:

- Added `docs/reference/AI_ENGINEERING_COMPETENCY_MAP_2026.md` to map the 12
  production AI engineering concepts to LiMa gates.
- The map covers prompt engineering, RAG, vector search, agents/tools,
  reasoning, memory, streaming/async, inference optimization, FinOps,
  fine-tuning, LLM eval, and MLOps/deployment.
- Policy retained: expand LiMa by measurable engineering controls, not
  prompt-only claims; fine-tuning remains gated behind eval data, privacy,
  retention, and rollback readiness.

Latest external capability radar agent/voice/design batch:

- Added VoxCPM, open-lovable, Hermes Agent Orange Book, refreshed goclaw, and
  claude-code-prompts to the external capability radar and roadmap.
- VoxCPM is Apache-2.0 and is admitted only as a later TTS/voice-design/
  controllable-cloning provider reference behind consent, model/weight review,
  serving budget, latency, and audio-retention gates.
- open-lovable and claude-code-prompts are MIT references for LiMa Code
  design reconstruction and prompt-contract work; both remain review/test
  gated and are not runtime dependencies.
- Hermes Agent Orange Book is CC BY-NC-SA and remains non-commercial
  concept-only; goclaw still has no reviewed license signal and remains
  concept-only for isolation/concurrency/security ideas.

Latest external capability radar research/subagent batch:

- Added last30days skill, LightRAG, Claude use cases, awesome-codex-subagents,
  AutoResearchClaw, OpenCode, and vibe-coding-cn to the external capability
  radar and roadmap.
- LightRAG is MIT and strengthens LiMa's graph/vector retrieval, multimodal
  parsing, chunking, and role-specific extraction/query/VLM roadmap.
- last30days, Claude use cases, and AutoResearchClaw strengthen research,
  use-case taxonomy, social/source search, HITL, benchmark, anti-fabrication,
  and budget-control planning.
- awesome-codex-subagents is MIT but remains a curated reference; LiMa still
  defaults to one owner agent plus bounded subagents, not broad auto-installed
  role libraries.
- OpenCode and vibe-coding-cn are MIT references for LiMa Code packaging,
  terminal/desktop UX, localization, Chinese onboarding, and planning-first
  vibe-coding workflow.

Latest external capability radar browser/search/RL batch:

- Added Hyperbrowser examples, Feishu `2026 企业级AI编程实践手册`,
  Sirchmunk, MiroFish, OpenClaw-RL, gstack, Nunchi agent-cli, and the official
  Hermes Agent site to the external capability radar and adoption roadmap.
- Sirchmunk is Apache-2.0 and strengthens raw-file/indexless search,
  evidence sampling, streaming search logs, self-evolving knowledge clusters,
  and path-allowlist planning.
- gstack is MIT and strengthens LiMa Code's stage-gated plan/review/QA/
  security/ship workflow, browser QA artifacts, safety guard commands, and
  cross-model second-opinion planning.
- OpenClaw-RL is Apache-2.0 and remains a future offline feedback/eval/
  training reference; live self-training is blocked until consent, privacy,
  eval, rollback, model-storage, compute, and cost gates exist.
- Hyperbrowser browser automation, Feishu methodology, Hermes Agent official
  site, MiroFish, and Nunchi agent-cli are admitted only as bounded references:
  scraping/API-key work is gated, Feishu has no observed reuse license,
  Hermes site license claims need source verification, MiroFish is AGPL
  concept-only, and trading/finance automation is blocked.

Latest external capability radar RAG/MCP/media batch:

- Added OpenRAG, Google Cloud generative-ai samples, RuVector, Agent-Reach,
  Qwen3-TTS, VidBee, cc-connect, bluebox, and Google MCP to the external
  capability radar, roadmap, MCP catalog, LiMa Code management notes, hardware
  companion references, and memory/progress logs.
- OpenRAG and Google Cloud generative-ai strengthen RAG ingestion,
  retrieval observability, grounding, managed-search, and sample/eval
  organization without making Langflow/OpenSearch or Google Cloud mandatory.
- RuVector is MIT and remains a benchmark-gated adaptive vector/graph memory
  reference; it cannot replace LiMa retrieval or storage without quality,
  latency, retention, and drift evidence.
- Agent-Reach, cc-connect, bluebox, Google MCP, and VidBee are admitted as
  default-off connector/media references. Cookie/social/proxy, messaging,
  closed-API extraction, cloud-resource MCP, and video downloading all require
  explicit account, credential, platform-term, cost, anti-abuse, and audit
  gates.
- Qwen3-TTS is Apache-2.0 source and strengthens the later voice/TTS roadmap;
  voice clone and custom voice remain behind model/API terms, explicit consent,
  latency/GPU, audio-retention, and safety gates.

Latest external capability radar hardware perception addendum:

- Added `ruvnet/RuView` to the external capability radar, hardware companion
  references, LiMa Code management notes, autonomy borrowing notes, roadmap,
  memory, and progress logs.
- RuView is MIT and is useful as a later ESP32/WiFi CSI ambient-perception
  reference: CSI firmware posture, edge sensing, Home Assistant/Matter bridge
  ideas, witness/evidence logs, and Codex/Claude workflow plugins.
- It is not a current runtime dependency and does not change the first
  writing-machine target. People sensing, through-wall sensing, vital-sign
  trends, fall/distress detection, room mapping, and security/medical outputs
  remain default-off behind consent, privacy/legal review, calibrated hardware
  evidence, false-positive policy, retention controls, and human review.

Latest external capability radar local data analysis addendum:

- Added `quelmap-inc/quelmap` to the external capability radar, LiMa Code
  management notes, autonomy borrowing notes, roadmap, memory, and progress
  logs.
- Quelmap is Apache-2.0 and is useful as a local data-analysis assistant
  reference: CSV/Excel/SQLite upload, table conversion, joins, visualization,
  statistical tests, Docker Compose packaging, local/Ollama defaults,
  OpenAI-compatible provider settings, Postgres storage, and Python sandbox UX.
- It is not a runtime dependency. Dataset contents/schema, generated Python,
  external database connections, and cloud LLM provider use remain gated by
  consent, redaction, read-only credentials, sandbox limits, data retention,
  and audit.

Latest external capability radar 10-subsystem addendum:

- Added `docs/reference/LIMA_10_SUBSYSTEM_OPEN_SOURCE_RECOMMENDATIONS.md` as
  the focused backlog for LiMa's 10 subsystems: coding worker/tool gateway,
  backend routing, context/RAG, memory, eval/quality, observability,
  security/governance, streaming/protocols, DevOps, and terminal UX.
- Existing radar projects such as OpenAI Agents SDK, Google ADK, Symphony,
  CubeSandbox, gstack, agent-skills, LightRAG, Agent Governance Toolkit,
  OpenCode, and Aider are de-duplicated and strengthened.
- New candidates such as E2B, GraphRAG, rerankers, FastEmbed, tree-sitter,
  Mem0, Letta, Promptfoo, DeepEval, OpenTelemetry, Prometheus, Guardrails AI,
  MCP Python SDK, A2A, Caddy, Nixpacks, Rich, and Textual are planning inputs
  only. Mixed-license, archived, unresolved, AGPL/LGPL, and source-available
  projects are explicitly gated before any dependency adoption.

Latest implementation/review planning addendum:

- Added `docs/superpowers/plans/2026-05-24-lima-implementation-review-plan.md`
  to convert recent learning into a developer-executes/Codex-reviews
  implementation plan.
- The plan orders work across router/key-pool telemetry, async/concurrency,
  context graph/reranking, memory taxonomy, eval/quality gates, observability,
  worker governance/MCP/A2A, sandbox evaluation, streaming, data workbench,
  DevOps/terminal UX, and later hardware companion expansion.
- Review ownership is explicit: the user implements one slice at a time; Codex
  reviews for bugs, regressions, tests, security, data leakage, permission
  expansion, architecture fit, and release readiness.

Latest LiMa Code CLI adaptation closeout:

- LiMa Code submodule advanced to `eaf30ce`
  (`fix: harden LiMa headless server integration`).
- The headless CLI no longer depends on fragile SSE-only parsing: it uses
  non-stream chat calls by default, preserves OpenAI JSON/SSE parsing, and
  accepts LiMa Server's Anthropic-style SSE text/tool events when encountered.
- Headless success now returns a non-empty `hls-...` session id and exits
  naturally with code 0 on Windows instead of hard `process.exit()`.
- Legacy external prompt telemetry remains disabled; tests assert no calls to
  `https://deepcode.vegamo.cn/api/plugin/new`.
- VPS route sync restored `/agent/learn/outcome`, then tightened it behind
  private Bearer auth. Public unauth POST returns 401; authenticated POST
  returns `{"ok":true,"recorded":true}`.
- Evidence: LiMa Code `npm.cmd run check`, `npm.cmd test`
  (`480 tests, 473 pass, 7 skipped`), `npm.cmd run build`, public headless
  smoke `lima_code_cli_smoke_ok` with exit code 0; main repo `ruff check .`,
  `pyright`, and full pytest `2141 passed, 10 skipped in 288.33s`.

Latest LiMa Code TUI workbench closeout:

- Added `/lima start` as a read-only operator workbench command in LiMa Code.
- The workbench gives the operator a clear first path: `/lima doctor`, local
  review, explicit test command, direct project Ask workflow, and server-task
  next/work commands.
- The welcome screen now renders fixed first-run actions for `/lima start`,
  `/lima doctor`, and direct project work instead of leaving discovery to
  random tips.
- Evidence: focused LiMa Code tests `47 passed`, `npm.cmd run typecheck`
  clean, `npm.cmd run lint` clean, `npm.cmd run format:check` clean,
  `npm.cmd run build` clean, and built CLI `/lima start` headless smoke
  returned `ok=true` with zero model calls.

Latest LiMa Code TUI vibe telemetry closeout:

- Referenced `esengine/DeepSeek-Reasonix` for visible request-layer feedback
  and token/cache meters, while keeping LiMa Code on its own LiMa Router
  transport path instead of adopting Reasonix's DeepSeek-only cache design.
- TUI waiting text now distinguishes LiMa Router waits from generic first-token
  waits and includes the active model plus retry/timeout telemetry.
- The TUI status line now shows active tokens and accumulated input, output,
  cache, and request counts from `usagePerModel`, so the operator can see
  where time and token budget are going.
- Evidence: focused LiMa Code TUI/session tests `71 tests, 68 pass, 3 skipped`;
  `npm.cmd run check` clean; full LiMa Code suite `498 tests, 491 pass,
  7 skipped`; `npm.cmd run build` clean with `dist/cli.js` 612.3kb.
- No VPS deploy was needed because no LiMa Server route, env, or deployment
  code changed in this slice.

Latest LiMa Code command-center TUI closeout:

- Selected A方案 from the ui-ux-pro-max TUI review: main chat remains the
  working surface, while runtime state becomes a visible operator layer.
- Added a pure runtime status view model for Router phase, model, thinking,
  active/input/output/cache/request usage, running tools, MCP readiness, and
  actionable risk labels including 401, 402, 429, timeout, and empty response.
- Wired a responsive `RuntimeStatusPanel` into the TUI: wide terminals show a
  right-side panel, medium terminals show a two-line band, and narrow terminals
  show a compact single-line summary.
- Evidence: focused runtime/status tests `5 passed`; `npm.cmd run check` clean;
  full LiMa Code suite `506 tests, 499 pass, 7 skipped`; `npm.cmd run build`
  clean with `dist/cli.js` 633.4kb; `git diff --check` clean.
- No VPS deploy was needed because this is LiMa Code CLI/TUI-only.

Latest LiMa Code npm package refresh:

- Rebuilt and re-uploaded `lima-code-0.1.24.tgz` after the command-center TUI
  slice.
- GitHub Release `lima-code-v0.1.24` now reports npm asset digest
  `sha256:1fb7afa1e080c61cad349abdcd4d2d8b8bdfcca09e2b34dd2f183c9372448d6f`.
- Public URL install smoke added 60 packages into a local temp prefix;
  installed `lima-code.cmd --version` returned `0.1.24`; installed
  `/lima start --json` returned `ok=true` with zero model calls.
- Installed dist contains the command-center runtime UI markers
  `RuntimeStatusPanel` and `402 quota/balance`.

Latest LiMa Code visible Chinese cleanup:

- Fixed remaining visible English in PromptInput placeholder/footer/status
  hints, raw-mode exit text, and `/lima doctor` report output.
- Internal doctor check ids remain machine-stable, but the operator report now
  renders Chinese labels such as `服务配置`, `服务连通`, `停止标记`, and
  `本地审计日志`.
- Evidence: focused tests `62 passed`; full LiMa Code suite
  `507 tests, 500 pass, 7 skipped`; `npm.cmd run check` clean;
  `npm.cmd run build` clean with `dist/cli.js` 635.2kb.
- GitHub Release `lima-code-v0.1.24` npm asset was refreshed again. Digest:
  `sha256:5eeeb390b2c90dc05d3dfb0466d254400f4813b74ee7f0b9711f60c07693730a`.
- Public URL install smoke confirmed Chinese `/lima doctor --json`; installed
  bundle no longer contains old `enter send` or `LiMa doctor: ready` strings.

Latest command execution/security hardening closeout:

- Added a shared `safe_command.py` command boundary and removed active
  `shell=True` execution from root service paths, LiMa vibecode scripts, and
  the ESP32 utility/example hits found by the full scan.
- Root launchers and smoke scripts no longer contain hardcoded LiMa API keys;
  they require `LIMA_API_KEY` or `LIMA_CODE_API_KEY` from the operator
  environment and fail clearly if missing.
- LiMa Code production dependency audit is clean after refreshing
  `deepcode-cli/package-lock.json`.
- Evidence: focused safety tests `29 passed`; root `ruff check .` clean;
  root `pyright` `0 errors`; root full pytest `2195 passed, 10 skipped`;
  `pip_audit` no known vulnerabilities; LiMa Code `npm.cmd run check` clean,
  `npm.cmd test` `497 tests, 490 pass, 7 skipped`, and
  `npm.cmd audit --omit=dev` `0 vulnerabilities`; VPS deployed 4 service files
  with health OK, public `/health` 200, and unauthenticated `/v1/models` 401.
