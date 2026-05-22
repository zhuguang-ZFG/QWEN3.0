# Personal Coding Assistant Progress

> Created: 2026-05-22

## 2026-05-22 Website Baseline

- Started persistent plan for closing chat/open-platform website issues.
- Reused prior evidence instead of repeating known-good checks blindly.
- Confirmed previous open-platform token test succeeded:
  - New API DB found at `/opt/new-api/one-api.db`.
  - Enabled channels point to `http://localhost:8080`.
  - Enabled tokens exist.
  - Local and public model/chat requests returned 200.
- Ran broader production audit for static assets, TLS/security headers, logs, backup, firewall exposure, and UI encoding.

## 2026-05-22 Production Audit And Closure

- Verified TLS expiry:
  - `chat.donglicao.com`: 2026-08-16 13:21:14 GMT.
  - `api.donglicao.com`: 2026-08-16 09:20:03 GMT.
- Found open platform title mojibake and fixed nginx sub_filter replacement.
- Found missing basic security headers and added them to chat/API nginx configs.
- Found chat `/quickstart/` serving fallback HTML for nested static paths and redirected it to `/`.
- Found direct public exposure risk for internal ports. Removed firewalld public ports `8080/3001` and added `eth0` direct reject rules for `3000/3001/3003/8080/8091`.
- Found New API backup cron overwriting a fixed dated file. Replaced it with dated daily backup and 14-day retention.
- Verified no regression:
  - Chat page/API non-stream/API stream all returned 200.
  - Open platform page/models/chat all returned 200 with valid token.
  - Internal localhost services still work for nginx.
  - Public direct internal ports are no longer reachable.

## 2026-05-22 Direction Reset

- User confirmed the product is a private personal coding assistant, not a commercial open platform.
- Added `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`.
- Removed billing/quota/usage commercial modules and commercial tests from the active worktree.
- Removed active payment, public registration, open-platform upgrade, commercial roadmap, and commercial readiness docs.
- Removed commercial wiring from `server.py`, `routes/admin.py`, and deploy preflight references.

## Next Personal Assistant Work

- Validate one real IDE or terminal-agent coding workflow against the private endpoint.
- Re-test failed providers when more backend keys/rate limits/local socket policy are healthy.

## 2026-05-22 Coding Backend Eval And Routing

- Added `coding_eval.py`, `scripts/eval_coding_backends.py`, and three coding fixtures under `evals/coding_cases/`.
- Added unit tests for case loading, candidate detection, grading, run failure handling, and Markdown report ranking.
- User challenged the first ranking as too narrow; expanded from the 10-backend shortlist to a full 85-candidate smoke.
- Broad smoke found 16 `code_review` passers.
- Ran full 3-case eval for those 16 passers:
  - 3/3 pass: `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, `or_gptoss_120b`.
  - Fast 80+ score under 800ms: `cerebras_gptoss`, `groq_gptoss`, `mistral_small`.
  - Useful 2/3 fallback tier: `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `mistral_medium`, `featherless`.
- Updated `code_orchestrator.POOLS` and `router_v3.POOLS["code"]` so the wider evidence-backed coding pool is tried first.
- Added Continue/VS Code detection to `routing_engine` and `router_v3`.
- Local IDE-routing smoke passed: `ide_source=Continue` produced `request_type=code_standard`, `scenario=coding`, backend `scnet_large_ds_flash`, and a real response in 1406ms.

## 2026-05-22 VPS Deployment

- Deployed the coding-routing changes to `/opt/lima-router` on VPS `47.112.162.80`.
- Uploaded runtime files only: `router_v3.py`, `routing_engine.py`, and `code_orchestrator.py`.
- Remote backup directory: `/opt/lima-router/backups/deploy-20260522_175739`.
- Remote `py_compile` passed for `router_v3.py`, `routing_engine.py`, `code_orchestrator.py`, and `server.py`.
- Restarted `lima-router` through `systemctl`.
- VPS local `/health` returned 200.
- VPS local OpenAI-compatible coding smoke returned 200 and routed to `github_gpt4o`.
- Public `https://chat.donglicao.com/v1/chat/completions` smoke returned 200 and routed to `cerebras_gptoss`.

## 2026-05-22 Claude Code Speed Fix

- Found the Claude Code slow path: requests with `tools` use the Anthropic `/v1/messages` tool branch, not the normal coding pool.
- Reordered `TOOL_TIER1_BACKENDS` to front-load fast tool-compatible backends: `groq_gptoss_20b`, `cerebras_gptoss`, `groq_gptoss`, GitHub, and Mistral.
- Changed tool backend retry behavior so one request tries distinct backends instead of retrying the same failed backend repeatedly.
- Added a regression test for distinct fast tool backend iteration.
- Deployed `server.py` to VPS with backup at `/opt/lima-router/backups/speed-20260522_181808`.
- Remote compile and `/health` passed after restart.
- VPS local Anthropic tool smoke returned 200 in 393ms with a real `tool_use` from `groq_gptoss_20b`.
- Public `https://chat.donglicao.com/v1/messages` tool smoke returned 200 in 819ms with a real `tool_use`.

## 2026-05-22 IDE Context Preflight

- Created `docs/superpowers/plans/2026-05-22-ide-context-preflight.md` and executed it task-by-task.
- Added `lima_context.py` with request-local context digest extraction for IDE source, workspace hints, task shape, language, file paths, and tool/error signals.
- Added `tests/test_lima_context.py` covering digest extraction, trivial-chat no-op behavior, max length, tool result summarization, and `code_orchestrator.enhance_context` integration.
- Injected the digest into normal coding route prompts through `code_orchestrator.enhance_context`.
- Injected the digest into Claude Code Anthropic `/v1/messages` tool requests through `server._inject_anthropic_context_preflight`.
- Kept the fast tool backend order and distinct-backend retry behavior intact.
- Local verification passed:
  - `python -m py_compile lima_context.py code_orchestrator.py server.py routing_engine.py router_v3.py`
  - `python -m pytest -q test_routing_engine.py test_rate_limiter.py test_http_caller.py test_streaming.py tests/test_coding_eval.py tests/test_lima_context.py` -> `70 passed in 0.51s`
- Deployed `server.py`, `code_orchestrator.py`, and `lima_context.py` to VPS with backup at `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Remote compile and `/health` passed after `systemctl restart lima-router`.
- Synced a no-BOM `code_orchestrator.py` copy after local cleanup with backup at `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- Final remote compile and `/health` passed after restart.
- Final public Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## 2026-05-22 Free Model Routing Refresh

- Checked whether all SCNet and Kimi-family free models were actually in use.
- Confirmed registration exists in `backends.py`, but routing did not actively use all working free capacity.
- Ran VPS smoke for SCNet/Kimi-family candidates:
  - Working: `scnet_ds_flash`, `scnet_ds_pro`, `scnet_qwen235b`, `scnet_qwen30b`, `cf_kimi_k26`.
  - Not production-live in smoke: `scnet_minimax`, `scnet_large_ds_flash`, `scnet_large_ds_pro`, `stock_kimi_k2`, `kimi`, `kimi_thinking`, `kimi_search`.
- Updated `code_orchestrator.py` and `router_v3.py` so VPS-working free SCNet models are active fallback capacity.
- Kept local proxy models registered but late because VPS ports `4504` and `4505` refused connections.
- Added `docs/FREE_MODEL_ROUTING_STATUS.md`.
- Added `docs/LIMA_MEMORY.md` as the detailed durable memory document.
- Local verification after route changes passed: `71 passed in 0.52s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- `systemctl restart lima-router` initially hung because uvicorn was waiting for open connections to close; fixed by `systemctl kill -s SIGKILL lima-router`, `systemctl reset-failed lima-router`, then `systemctl start lima-router`.
- VPS `/health` returned 200 after recovery.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## 2026-05-22 SCNet/Kimi First-Tier Eval

- Created `docs/superpowers/plans/2026-05-22-free-model-first-tier-eval.md`.
- Ran a VPS-side three-case coding fixture against SCNet and Kimi-family candidates.
- SCNet direct first-tier winners:
  - `scnet_ds_flash`: 3/3, avg score 100, avg latency 3330ms.
  - `scnet_qwen235b`: 3/3, avg score 100, avg latency 4004ms.
  - `scnet_qwen30b`: 3/3, avg score 91, avg latency 2713ms.
  - `scnet_ds_pro`: 3/3, avg score 91, avg latency 4571ms.
- Kimi did not meet first-tier criteria:
  - `cf_kimi_k26`: 1/3, avg score 48, avg latency 7844ms.
  - local `kimi`, `kimi_thinking`, `kimi_search`: VPS proxy `4504` refused connections.
  - `stock_kimi_k2`: invalid response.
- Updated `code_orchestrator.py` and `router_v3.py` to move direct SCNet winners into coding first tier.
- Added `data/free_model_first_tier_eval.json` with the summary evidence.
- Local verification passed after routing change: `71 passed in 0.59s`.
- Deployed `code_orchestrator.py` and `router_v3.py` to VPS with backup at `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Remote compile passed; `lima-router` restarted cleanly; VPS `/health` returned 200.
- VPS route order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## 2026-05-22 Local Proxy And FRP Closure

- Corrected the earlier proxy diagnosis: Kimi and SCNet-large are Windows-local services, not VPS-local services.
- Updated `local_router_start.bat` so it starts `D:\GIT\server.py` on Windows port `8080` and then starts `frpc.exe` if needed.
- Verified Windows `4505` SCNet-large models and chat completion locally.
- Verified Windows `4504` Kimi models locally; chat currently fails with `chat.anonymous_usage_exceeded`, so Kimi needs session refresh.
- Verified `frpc.exe` registers `redcode-api`.
- After VPS `8088/tcp` was opened, verified public FRP path:
  - `http://47.112.162.80:8088/health`: 200.
  - `http://47.112.162.80:8088/v1/models`: 200.
  - `http://47.112.162.80:8088/v1/chat/completions`: 200.
- Added `docs/LOCAL_PROXY_RUNTIME_STATUS.md`.

## 2026-05-22 Documentation And Next Roadmap

- Updated source-of-truth docs for the personal coding assistant direction.
- Added `docs/DOCUMENTATION_STATUS.md` to mark active docs versus historical commercial/open-platform docs.
- Added `docs/FREE_WEB_AI_EXPANSION_PLAN.md` for the next phase:
  - find more no-login web AI candidates like DuckAI and HeckAI;
  - improve token/session refresh, rate limiting, and quota handling;
  - optimize routing so free backends are selected by quality, health, latency, quota, and task fit.
- Added `docs/superpowers/plans/2026-05-22-free-web-ai-stability-routing.md` as the executable Superpowers implementation plan.
- Verification:
  - `git diff --check` passed with line-ending warnings only.
  - Core suite passed with `pytest --ignore=active_model`: `66 passed, 5 skipped`.
  - Plain pytest collection is blocked by stale junction `D:\GIT\active_model`.
  - Public FRP health/models/chat smokes on `http://47.112.162.80:8088` returned 200.

## 2026-05-22 Free Web AI Sandbox Probe

- Created branch `codex/free-web-ai-probe`.
- Added candidate registry:
  - `data/free_web_ai_candidates.json`
  - `docs/free-web-ai-candidates.md`
- Added sandbox probe harness:
  - `scripts/probe_free_web_ai.py`
  - `tests/test_free_web_ai_probe.py`
- TDD verification:
  - RED: `tests/test_free_web_ai_probe.py` failed with missing `scripts.probe_free_web_ai`.
  - GREEN: `4 passed in 0.05s`.
- Reachability probe:
  - Command: `D:\GIT\venv\Scripts\python.exe scripts\probe_free_web_ai.py --timeout 20`.
  - Output: `data/free_web_ai_probe_results.json`.
  - Result: 6/6 candidate pages returned HTTP 200.
- Added failure-state classification to `health_tracker.py`.
- Updated `http_caller.py` so backend error text reaches `health_tracker.record_failure`.
- Focused verification passed: `6 passed in 0.07s` for new probe tests plus health-state tests.
- Full branch verification passed:
  - `72 passed, 5 skipped` with `pytest --ignore=active_model`.
  - JSON registry/results validation passed.
  - Probe dry-run listed six candidates.
  - FRP `/health` returned 200.

## 2026-05-22 Local Reverse AI Inventory

- Audited local ports/processes:
  - `4500` DuckAI, `4502` TheOldLLM, `4503` g4f, `4504` Kimi, `4505` SCNet-large, `8080` LiMa, `11434` Ollama.
- Verified DuckAI is already reversed in `D:\duckai`; `/v1/models` and user-only chat pass locally.
- Reproduced DuckAI LiMa-format blocker: empty OpenAI `system` message causes upstream 400.
- Verified SCNet-large `4505` models and chat pass locally.
- Verified Kimi `4504` models pass but chat returns `chat.anonymous_usage_exceeded`.
- Verified TheOldLLM `4502` models pass but local chat timed out after 30 seconds.
- Verified g4f `4503` default chat works, while one explicit PollinationsAI model mapping failed.
- Recorded inventory in:
  - `docs/LOCAL_REVERSE_AI_STATUS.md`
  - `data/local_reverse_ai_inventory.json`
  - `docs/superpowers/plans/2026-05-22-local-reverse-ai-integration.md`
- Updated candidate docs so DuckAI is no longer treated as net-new reverse work and HeckAI is marked as an existing adapter draft.

## 2026-05-22 Local Reverse AI Integration

- Added RED/GREEN coverage for OpenAI `no_system` body construction.
- Updated `http_caller.py` so DuckAI-style OpenAI backends omit `role=system` and preserve non-empty system/IDE context in the first user message.
- Marked DuckAI backends `no_system` and registered the three missing local DuckAI models.
- Kept DuckAI models late in `router_v3.py` and `code_orchestrator.py` fallback order.
- Ran DuckAI local coding admission with dedicated output:
  - `data/ddg_route_admission_eval.json`
  - `docs/DDG_ROUTE_ADMISSION.md`
  - `ddg_gpt4o_mini` and `ddg_gpt5_mini`: 3/3.
  - `ddg_claude_haiku_45`: strict JSON failure.
  - `ddg_tinfoil_gptoss_120b`: upstream 500/cooldown.
- Confirmed Kimi chat still returns `chat.anonymous_usage_exceeded` and health state is `manual_refresh_required`.
- Ran SCNet-large local route eval with dedicated output:
  - `data/scnet_large_route_eval.json`
  - `docs/SCNET_LARGE_ROUTE_EVAL.md`
  - `scnet_large_ds_flash` and `scnet_large_ds_pro`: both 3/3.
- Reproduced TheOldLLM local `4502` 30s chat timeout and left it late until refresh/log safety plus upstream diagnosis are closed.

## 2026-05-22 Claude Code LiMa Tool-Loop Incident

- Reproduced healthy baseline:
  - Claude CLI simple prompt returned `claude-cli-ok`.
  - Claude CLI `Read D:\GIT\routing_engine.py` returned `read-loop-ok`.
  - Claude CLI stream-json `Read D:\GIT\server.py` returned `read-server-ok`.
- Identified unguarded protocol boundary in `server.py`: empty or malformed OpenAI-style upstream tool responses could become Anthropic HTTP 200 responses with empty `content`.
- Added failing regression tests in `tests/test_anthropic_tool_protocol.py`; initial run failed 4/4.
- Hardened `_convert_response_openai_to_anthropic()` and simulated Anthropic SSE `tool_use` block starts.
- Verification:
  - `tests/test_anthropic_tool_protocol.py`: `4 passed`.
  - Focused suite: `90 passed, 5 skipped`.
  - VPS backup: `/opt/lima-router/backups/claude-tool-protocol-20260522_220037`.
  - VPS health: 200.
  - Public `/v1/messages`: exact `deployed-msg-ok`.
  - Real Claude CLI large-file `Read`: exact `deployed-read-ok`.
  - FRP health: 200.

## 2026-05-22 P0 Router Hardening

- Created `docs/superpowers/plans/2026-05-22-p0-router-hardening.md` before code changes.
- Added RED tests:
  - `tests/test_access_guard.py` for private key parsing, missing-auth rejection, configured-key acceptance, unconfigured fail-closed behavior, and admin fail-closed behavior.
  - `tests/test_fallback_context.py` for preserving full messages during fallback backend retries.
- Verified RED: focused run failed because `access_guard` did not exist yet.
- Implemented `access_guard.py`:
  - Reads `LIMA_API_KEY`.
  - Reads comma-separated `LIMA_API_KEYS`.
  - Accepts either `Authorization: Bearer <key>` or raw `Authorization: <key>`.
  - Fails closed with 503 if no private key is configured.
  - Returns 401 for missing or invalid authorization.
- Wired the guard into `server.py` for:
  - `/v1/chat/completions`
  - `/v1/messages`
  - `/api/live-key`
  - `/v1/status`
- Kept `/health` and `/v1/models` unauthenticated for smoke checks and IDE model discovery.
- Changed `routes/admin.py` so missing `LIMA_ADMIN_TOKEN` returns 503 instead of allowing admin access.
- Updated `_try_backend()` to accept full `messages` and changed same-tier plus upgrade fallback call sites to pass `messages_to_dicts(req.messages)`.
- Fixed `_detect_ide()` so ordinary chat messages return an empty string instead of a truthy unknown marker.
- Added `tests/test_ide_detection.py` to prevent ordinary requests from being treated as IDE traffic.
- Protected `/v1/images/generations` with the same private API key guard.
- Added `tests/test_image_endpoint_guard.py` and capped image dimensions at 2048x2048.
- Added `tests/test_stream_footer.py` with RED/GREEN coverage for Anthropic speculative and fake stream paths.
- Removed client-visible backend footers from Anthropic streaming responses; backend names stay available to internal request logging.
- Reworked `test_streaming.py` so its async generator checks run via `asyncio.run()` instead of being skipped when `pytest-asyncio` is not installed/configured.
- Verification:
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_access_guard.py tests\test_fallback_context.py -q --ignore=active_model`: `6 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_ide_detection.py tests\test_image_endpoint_guard.py -q --ignore=active_model`: `4 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_stream_footer.py -q --ignore=active_model`: `2 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m pytest test_streaming.py -q --ignore=active_model`: `5 passed`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile access_guard.py server.py routes\admin.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile test_streaming.py`: passed.
  - Core suite with new tests: `112 passed`.
- Caveat:
  - This increment is local only and has not been deployed to VPS.

## 2026-05-22 Superpowers Plan Closure Review

- Reconciled historical Superpowers plan checkboxes:
  - `2026-05-22-cloudflare-workers-ai-routing.md`
  - `2026-05-22-token-safe-local-proxy-routing.md`
  - `2026-05-22-free-model-first-tier-eval.md`
- Added `docs/superpowers/PLAN_CLOSURE_STATUS.md` to classify each plan as closed, local closed, non-goal, or deferred risk.
- Current judgment:
  - Main `task_plan.md` phases are complete.
  - Historical Superpowers execution plans are checkbox-reconciled.
  - P0 router hardening was local closed at this point; it was deployed in the later explicit VPS deployment pass.

## 2026-05-22 P0 Router Hardening VPS Deployment

- Pushed commit `c4515d3` to `origin/codex/free-web-ai-probe`.
- Deployed P0 runtime files to VPS after explicit user approval:
  - `server.py`
  - `access_guard.py`
  - `routes/admin.py`
- Backup: `/opt/lima-router/backups/p0-router-hardening-20260522_230407`.
- Remote `.env` did not have `LIMA_API_KEY` or `LIMA_API_KEYS`; added `LIMA_API_KEY` so the fail-closed private guard would not break authorized IDE/API clients.
- Remote compile passed for `server.py`, `access_guard.py`, and `routes/admin.py`.
- `lima-router` restarted active.
- First smoke immediately after restart hit a short connection-refused window before uvicorn listened; follow-up service status showed the process active and listening on `0.0.0.0:8080`.
- Public authorized OpenAI and Anthropic smokes initially returned 500.
- Root cause: VPS `health_tracker.py` was stale and lacked `get_backend_state()`, while current `routing_engine.py` calls it.
- Synced `health_tracker.py`:
  - Backup: `/opt/lima-router/backups/health-tracker-sync-20260522_230937`.
  - Remote compile passed for `health_tracker.py`, `routing_engine.py`, `server.py`, `access_guard.py`, and `routes/admin.py`.
  - `lima-router` restarted active.
- Final smoke:
  - Public `/v1/chat/completions` without auth returned 401.
  - Public `/v1/chat/completions` with auth returned exact `p0-deploy-ok`.
  - Public `/v1/messages` with auth returned exact `p0-msg-ok`.
  - FRP `http://47.112.162.80:8088/health` returned 200.

## 2026-05-23 Code Quality Hardening Evidence Closure

- Closed Task 5 of `docs/superpowers/plans/2026-05-22-code-quality-correctness-hardening.md` as a documentation and evidence-only pass.
- Accepted/fixed findings:
  - `smart_router._has_vision_content` was disconnected; the `cf_vision` image path is restored and covered by `tests/test_vision_routing.py`.
  - Anthropic vision stats now measure duration from the real request start; `tests/test_request_stats.py` covers the helper and `/v1/messages` image branch.
  - `_record_request()` performs IP location lookup outside `_stats_lock`, while stats writes stay inside the lock.
  - Local one-off deploy/debug/run/stress probes are protected by root-anchored `.gitignore`; tracked `scripts/` hardcoded `sk-` literals were replaced by environment reads.
- Rejected/outdated findings:
  - Admin API routes are not unauthenticated after P0; HTML admin shell review remains separate.
  - Current `deploy_v3.py` uses `LIMA_DEPLOY_PASS` or key path, not a plaintext deploy password.
  - The old `test_streaming.py` issue is stale because P0 executed and passed it.
- Deferred follow-ups:
  - Split `server.py`.
  - Establish a `BACKENDS` single source.
  - Deduplicate response-builder logic.
  - Migrate `smart_router.cb_*` state into `health_tracker`.
- Security note: any previously exposed tokens should be rotated; no token values were copied into docs.
- Deployment policy: this round is local-only unless the user explicitly requests deploy later.
- Verification:
  - `git -C D:\GIT diff --check`: passed without whitespace errors; warning-only CRLF notices appeared for unrelated dirty files `backends.py`, `budget_manager.py`, `capability_matrix.py`, and `router_v3.py`.
  - `D:\GIT\venv\Scripts\python.exe -m py_compile smart_router.py server.py`: passed.
  - `D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model`: `5 passed`.
  - Core suite: `117 passed`.
  - `git -C D:\GIT grep -n "sk-" -- scripts`: no output, expected for no matches.
