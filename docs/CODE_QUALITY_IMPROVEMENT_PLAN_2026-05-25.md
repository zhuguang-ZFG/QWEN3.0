# LiMa Code Quality Improvement Plan

> Date: 2026-05-25
> Updated: 2026-05-26
> Scope: current `D:\GIT` LiMa server workspace after commits through `db50e01`.
> Purpose: review the pending `CLAUDE.md` update and turn remaining code-quality findings into executable improvement slices.

## Implementation Status (2026-05-26)

| ID | Status | Evidence |
|---|---|---|
| P0.1 chunked body limit | **Done** | `BodySizeLimitMiddleware` in `server.py`; `tests/test_http_body_limit.py` |
| P0.2 `/api/live-key` | **Done** | metadata-only in `routes/system_endpoints.py`; `tests/test_system_endpoints.py` |
| P0.3 `key_rotation` | **Done** | stub in `deploy/key_rotation.py`; legacy in `scripts/archive/key_rotation_legacy.py` |
| P1.1 semantic cache | **Done** | `_log.warning` + `db_write_errors`; `tests/test_semantic_cache.py` |
| P1.2 admin login | **Done** | `constant_time_equals` in `routes/admin.py` |
| P1.3 silent catches | **In progress** | 2026-05-26: `media_inbound`, `health_recorder`, `chat_post_closeout`, `admin_api` |
| P2+ file split / routing | **Backlog** | see sections below |

## Current Verification Snapshot

Commands run during this review:

```powershell
python -m py_compile server.py http_body_limit.py routes/chat_handler.py routes/chat_handler_dispatch.py routes/chat_endpoints.py routes/anthropic_messages_handler.py routes/tool_forward.py routes/tool_forward_stream.py converters/anthropic_format.py
python -m pytest tests/test_http_body_limit.py tests/test_tool_forward_failures.py tests/test_anthropic_format_tools.py tests/test_anthropic_tool_protocol.py tests/test_chat_endpoints.py tests/test_repo_hygiene.py
python -m pytest
git diff --check
```

Results:

- Focused tests: `18 passed`.
- Full suite: `1471 passed, 10 skipped`.
- `git diff --check`: clean.
- Before this plan was written, the only local dirty file was `CLAUDE.md`.

## CLAUDE.md Change Review

Overall assessment: the pending `CLAUDE.md` update is directionally useful. It reflects the recent decomposition work and highlights several real safety and maintainability risks. It should not be treated as fully precise yet because several counts and some risk labels drift from the current repository state.

### Accurate Or Useful Claims

| Claim | Review |
|---|---|
| `server.py` is now a thin FastAPI entrypoint. | Correct. Current `server.py` is about 114 lines and mostly wires middleware, route dependencies, and route registration. |
| `smart_router.py`, `http_caller.py`, and `health_tracker.py` were substantially split. | Correct. Current counts are approximately `smart_router.py` 196, `http_caller.py` 33, `health_tracker.py` 82. |
| `router_http.py`, `routes/agent_tasks.py`, `code_orchestrator.py`, and `session_memory/store.py` remain over the 300-line project target. | Correct. Current counts: `router_http.py` 362, `routes/agent_tasks.py` 489, `code_orchestrator.py` 327, `session_memory/store.py` 431. |
| `/api/live-key` returns a raw provider key. | Correct. `routes/system_endpoints.py` returns `GOOGLE_AI_KEY` after LiMa private auth. This is still a credential exposure boundary. |
| `deploy/key_rotation.py` exposes local HTTP key/state endpoints without API auth. | Correct. It binds `127.0.0.1:8909`, but local callers can read raw keys/state. |
| `semantic_cache.py` silently ignores SQLite write failures. | Correct. `SemanticCache.put()` catches broad `Exception` and does `pass`. |
| `deploy_v3.py` uses `AutoAddPolicy()` and `pkill -9`. | Correct. Treat as legacy/manual script risk unless replaced by reviewed bundle deploy flow. |

### Claims That Need Correction

| Claim In CLAUDE.md | Current Evidence | Suggested Correction |
|---|---:|---|
| `~66,500` Python source lines excluding `venv/deepcode-cli/esp32/donglicao`. | Current measured value is about `54,516` lines under the same exclusions. | Regenerate the count or mark it approximate with the command used. |
| `137` test files. | Current measured `tests/test_*.py` count is `135`; all repo `test_*.py` outside excluded dirs is `146`. | Specify whether the count is only `tests/` or all repo test files. |
| `41` top-level subdirectories. | Current filtered top-level directory count is `40`. | Update to `40`, or document the inclusion rules. |
| `routes/` is `6076` lines. | Current measured routes Python lines are about `5260`. | Update route totals. |
| Several individual line counts. | Some are stale: `routes/chat_endpoints.py` 163, `routes/chat_handler.py` 96, `routes/chat_handler_dispatch.py` 283, `routes/ops_metrics.py` 289, `routes/system_endpoints.py` 52. | Recompute before committing CLAUDE.md. |
| `routes/admin.py` token comparison is non-constant-time. | Partly correct: `admin_login()` still uses `token != get_admin_token()`, but other private API guards use constant-time compare. | Phrase narrowly: "admin login form token check still uses direct string comparison." |
| `coding_eval.py compile() risk`. | It uses `compile()` for syntax grading only, not execution. | Downgrade to "safe enough currently; keep compile-only and never exec generated code." |

## Improvement Backlog

### P0.1 Fix Chunked Body Limit Enforcement

Problem:

- `http_body_limit.py` wraps a new `Request` with `limited_receive`, then passes it to `call_next`.
- Integration testing shows chunked JSON bodies can still reach the endpoint in full.
- Repro during review: `max_size=15`, chunked body length 28, endpoint returned 200 and saw all 28 bytes.

Files:

- `http_body_limit.py`
- `server.py`
- `tests/test_http_body_limit.py`

Implementation steps:

1. Add a failing integration test using `TestClient(..., raise_server_exceptions=False)` with generator content and `Transfer-Encoding: chunked`.
2. Replace the current request-object wrapping with an ASGI middleware that wraps the `receive` callable before Starlette constructs downstream request bodies, or implement a route middleware pattern proven by the new integration test.
3. Ensure oversized chunked bodies return `413`, not `500`.
4. Ensure normal chunked JSON under the cap still returns `200`.
5. Keep the declared `Content-Length` fast-path rejection.

Verification:

```powershell
python -m pytest tests/test_http_body_limit.py tests/test_chat_endpoints.py
python -m pytest
git diff --check
```

VPS gate:

- Deploy only after local full suite passes.
- Public smoke should include normal `/v1/messages` and `/v1/chat/completions`.
- Optional negative smoke: oversized chunked request should return `413`.

### P0.2 Remove Raw Provider Key From `/api/live-key`

Problem:

- `routes/system_endpoints.py` returns the raw `GOOGLE_AI_KEY`.
- Even though the route requires LiMa private auth, it expands blast radius from "can call LiMa" to "can exfiltrate upstream provider credential".

Files:

- `routes/system_endpoints.py`
- Any frontend/client that currently calls `/api/live-key`
- `tests/test_system_endpoints.py`
- `docs/GEMINI_LIVE_PLAN.md`

Preferred direction:

1. Replace `/api/live-key` with a server-side Live session proxy or short-lived session token flow.
2. If a proxy is too large for the slice, change endpoint behavior to return capability metadata only and fail closed for raw key access.
3. Add a regression test that response JSON never contains `GOOGLE_AI_KEY`.
4. Update docs that currently describe "dynamic key fetch".

Verification:

```powershell
python -m pytest tests/test_system_endpoints.py tests/test_secret_hygiene.py
python -m pytest
git diff --check
```

### P0.3 Harden Or Retire `deploy/key_rotation.py`

Problem:

- Local HTTP endpoints expose raw keys and full state without authentication.
- It scrapes third-party free keys and stores valid keys in `/opt/lima-router/key_pool.json`.
- This is operationally fragile and inconsistent with LiMa's current evidence-driven, private-backend direction.

Files:

- `deploy/key_rotation.py`
- `docs/BACKEND_OVERVIEW.md`
- `docs/WORKSPACE_HYGIENE.md` if runtime storage guidance changes

Implementation options:

| Option | Recommendation | Work |
|---|---|---|
| Retire script | Preferred if unused in production. | Move to `scripts/archive/` or delete after confirming no systemd/service reference. |
| Keep local only | Acceptable short term. | Add bearer auth from env, redact `/status`, never return raw keys except to a privileged local caller. |
| Integrate with `key_pool.py` | Later only. | Convert to explicit provider-pool loader with tests and no scraping of questionable sources by default. |

Verification:

```powershell
python -m py_compile deploy/key_rotation.py
python -m pytest tests/test_secret_hygiene.py tests/test_repo_hygiene.py
rg -n '"key": key|FREETHEAI_KEY|pekpik_current' deploy/key_rotation.py
```

### P1.1 Make Semantic Cache Failures Observable

Problem:

- `semantic_cache.py` hides SQLite write failures.
- Cache failure does not break chat, but it can silently erase a performance feature and hide DB lock/disk-full issues.

Files:

- `semantic_cache.py`
- `tests/test_context_cache.py` or a new `tests/test_semantic_cache.py`

Implementation steps:

1. Add module logger.
2. On DB write failure, log `warning` with exception type and cache key prefix only.
3. Add counters for `db_write_errors` in `stats()`.
4. Add tests with a monkeypatched DB object that raises on `execute()`.

Verification:

```powershell
python -m pytest tests/test_context_cache.py tests/test_system_endpoints.py
python -m pytest
```

### P1.2 Fix Admin Login Constant-Time Comparison

Problem:

- `routes/admin.py` login form still uses direct string comparison.
- The high-value API guards already use `constant_time_equals`; admin login should match that style.

Files:

- `routes/admin.py`
- `tests/test_admin_csrf.py`
- `tests/test_admin_paths.py`

Implementation steps:

1. Use `access_guard.constant_time_equals()` for token validation.
2. Keep fail-closed behavior when `LIMA_ADMIN_TOKEN` is missing.
3. Add/adjust test that patches the compare helper and verifies it is called.

Verification:

```powershell
python -m pytest tests/test_admin_csrf.py tests/test_admin_paths.py tests/test_admin_ui.py
```

### P1.3 Replace Bare `except` And Silent Broad Catches In Active Paths

Problem:

- Silent catches remain in several production-adjacent modules.
- These are sometimes intentional best-effort behavior, but they need traceability.

Initial target list:

- `semantic_cache.py`
- `routes/telegram.py`
- `routes/telegram_commands.py`
- `server_lifespan.py`
- `routes/chat_preflight.py`
- `routes/chat_handler_dispatch.py`

Implementation rule:

- If failure is non-critical, log `warning` or increment an observable counter.
- If failure means a feature is disabled, expose it in health/ops metrics.
- Avoid logging prompts, tokens, or raw provider errors that may include secrets.

Verification:

```powershell
rg -n 'except Exception:\\s*$|except:\\s*$' <touched-files>
python -m pytest <focused tests>
python -m pytest
```

### P2.1 Continue File-Size Decomposition

Remaining production files over 300 lines:

| File | Current Lines | Suggested Split |
|---|---:|---|
| `routes/agent_tasks.py` | 489 | store, schemas, lifecycle routes, review/evolution hooks |
| `agent_runtime/orchestrator.py` | 491 | queue model, lease handling, persistence, recovery |
| `session_memory/store.py` | 431 | schema/init, CRUD, query helpers, test reset |
| `backends.py` | 387 | provider definitions, route pools, capability lists |
| `router_http.py` | 362 | either migrate live callers to `http_*` modules or archive legacy code |
| `code_orchestrator.py` | 327 | planning/context, tier execution, fallback policy |
| `routes/quality_gate.py` | 306 | typed result checks, response heuristics, fallback API |
| `routes/device_gateway.py` | 302 | HTTP routes, WebSocket loop, event projection |

Slice rule:

- One extraction slice should preserve behavior, add import-compatibility tests, and avoid route/deployment changes unless needed.
- Do not combine decomposition with feature changes.

### P2.2 Resolve Routing Duality

Problem:

- `smart_router`, `routing_engine`, `router_v3`, `router_http`, and `http_*` modules all still exist.
- Some duality is compatibility, but the authority boundary should be explicit.

Plan:

1. Document the authoritative request pipeline in `docs/REQUEST_PIPELINE_AUTHORITY.md`.
2. Add tests that assert which module owns:
   - backend selection;
   - health/cooldown gating;
   - HTTP invocation;
   - response cleanup;
   - retrieval injection.
3. Mark legacy facades in module docstrings.
4. Remove or archive unused legacy entry points only after coverage proves no imports rely on them.

### P2.3 Add Structured Fixture Groups For Tests

Problem:

- Test coverage is strong, but `tests/` is flat and hard to navigate.
- Current count is large enough that future ownership is fuzzy.

Plan:

1. Keep existing test filenames stable.
2. Add `tests/README.md` with ownership map:
   - request protocol;
   - routing;
   - device gateway;
   - agent runtime;
   - memory/retrieval;
   - ops/security.
3. Add shared fixtures only where they remove clear duplication.
4. Avoid a broad test move unless import paths and CI are updated in one slice.

### P3.1 Keep `CLAUDE.md` As A Short Contributor Guide

Problem:

- The pending update turns `CLAUDE.md` into a large audit inventory.
- That is useful, but it will drift quickly and may bury the operating rules.

Recommendation:

1. Keep `CLAUDE.md` concise: project direction, safety rules, top commands, and links.
2. Move volatile inventory and risk tables to this document or a dated audit doc.
3. Add a "Regenerate Statistics" command block if line counts remain in `CLAUDE.md`.

Suggested command block:

```powershell
$files = rg --files -g '*.py' -g '!venv/**' -g '!deepcode-cli/**' -g '!esp32S_XYZ/**' -g '!donglicao-site/**' -g '!__pycache__/**'
$count = ($files | Measure-Object).Count
$lines = 0
foreach ($f in $files) { $lines += (Get-Content -Encoding UTF8 $f | Measure-Object -Line).Lines }
"python_files=$count"
"python_lines=$lines"
```

## Recommended Execution Order

1. P0.1 body limit integration bug.
2. P0.2 `/api/live-key` raw key exposure.
3. P0.3 key rotation endpoint hardening or retirement.
4. P1.1 semantic cache observability.
5. P1.2 admin login constant-time comparison.
6. P1.3 silent catch cleanup in active paths.
7. P2.1 file-size decomposition by module ownership.
8. P2.2 routing authority cleanup.
9. P2.3 test ownership map.
10. P3.1 trim or split `CLAUDE.md` inventory.

## Closeout Criteria For Each Slice

Every slice should include:

- focused regression tests for the touched behavior;
- touched-file compile check;
- `git diff --check`;
- full `python -m pytest` when production Python changed;
- secret/hygiene scan when endpoints, deploy scripts, or credentials are touched;
- VPS deploy and public smoke only when request routing, auth, deployment, Device Gateway, or production path behavior changes.
